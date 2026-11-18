from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .agent.runner import AgentRunner
from .auth import AuthTokenError, SignedAuthService, USER_ID_PATTERN, UserIdentity
from .business import BusinessGateway, HttpUmbrellaBusinessGateway
from .config import DEFAULT_AUTH_SECRET, Settings
from .memory.repository import MemoryRepository
from .memory.service import MemoryService
from .memory.types import MEMORY_LABELS
from .model_gateway.factory import create_model_gateway
from .model_gateway.protocol import ModelGateway
from .model_gateway.repository import ModelCallRepository
from .observability.repository import TraceRepository
from .observability.service import TraceService
from .repository import ConversationNotFoundError, SQLiteConversationRepository
from .schemas import (
    AuthUserDTO,
    ConversationDTO,
    CreateConversationRequest,
    DeleteMemoriesResponse,
    DemoSessionRequest,
    ExchangeLaunchTokenRequest,
    MessageDTO,
    ModelSpanDTO,
    SendMessageRequest,
    ToolSpanDTO,
    TraceDetailDTO,
    TraceSummaryDTO,
    TurnTraceDTO,
    UserMemoryDTO,
)
from .sse import stream_support_reply
from .tools.executor import ToolExecutor
from .tools.repository import ToolCallRepository


def create_app(
    settings: Settings | None = None,
    business_gateway: BusinessGateway | None = None,
    model_gateway: ModelGateway | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_environment()
    if resolved_settings.environment.lower() == "production":
        if not resolved_settings.auth_required:
            raise ValueError("APP_AUTH_REQUIRED=true is required in production")
        if resolved_settings.auth_secret == DEFAULT_AUTH_SECRET:
            raise ValueError("APP_AUTH_SECRET must be changed in production")
        if not resolved_settings.auth_cookie_secure:
            raise ValueError("APP_AUTH_COOKIE_SECURE=true is required in production")
    auth_service = SignedAuthService(
        secret=resolved_settings.auth_secret,
        launch_ttl_seconds=resolved_settings.auth_launch_ttl_seconds,
        session_ttl_seconds=resolved_settings.auth_session_ttl_seconds,
    )
    repository = SQLiteConversationRepository(resolved_settings.database_path)
    owns_business_gateway = business_gateway is None
    resolved_business_gateway = business_gateway or HttpUmbrellaBusinessGateway(
        base_url=resolved_settings.business_base_url,
        internal_token=resolved_settings.business_internal_token,
        timeout_seconds=resolved_settings.business_timeout_seconds,
    )
    model_call_repository = ModelCallRepository(resolved_settings.database_path)
    owns_model_gateway = model_gateway is None
    resolved_model_gateway = model_gateway or create_model_gateway(
        resolved_settings,
        model_call_repository,
    )
    tool_call_repository = ToolCallRepository(resolved_settings.database_path)
    memory_repository = MemoryRepository(resolved_settings.database_path)
    memory_service = MemoryService(
        repository=memory_repository,
        conversation_repository=repository,
        recent_message_limit=resolved_settings.memory_recent_message_limit,
        summary_max_chars=resolved_settings.memory_summary_max_chars,
        max_long_term_items=resolved_settings.memory_max_long_term_items,
    )
    trace_repository = TraceRepository(resolved_settings.database_path)
    trace_service = TraceService(trace_repository)
    tool_executor = ToolExecutor(
        gateway=resolved_business_gateway,
        repository=tool_call_repository,
    )
    agent_runner = AgentRunner(
        executor=tool_executor,
        max_tool_calls=resolved_settings.agent_max_tool_calls,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await repository.initialize()
        await model_call_repository.initialize()
        await tool_call_repository.initialize()
        await memory_repository.initialize()
        await trace_repository.initialize()
        try:
            yield
        finally:
            if owns_business_gateway and isinstance(
                resolved_business_gateway,
                HttpUmbrellaBusinessGateway,
            ):
                await resolved_business_gateway.close()
            if owns_model_gateway:
                await resolved_model_gateway.close()

    app = FastAPI(title="Agent Support API", version="0.4.0", lifespan=lifespan)
    app.state.repository = repository
    app.state.settings = resolved_settings
    app.state.business_gateway = resolved_business_gateway
    app.state.model_gateway = resolved_model_gateway
    app.state.model_call_repository = model_call_repository
    app.state.tool_call_repository = tool_call_repository
    app.state.agent_runner = agent_runner
    app.state.memory_repository = memory_repository
    app.state.memory_service = memory_service
    app.state.trace_repository = trace_repository
    app.state.trace_service = trace_service
    app.state.auth_service = auth_service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Demo-User", "X-Request-ID"],
    )

    def session_identity(
        session_token: str | None = Cookie(
            default=None,
            alias=resolved_settings.auth_cookie_name,
        ),
    ) -> UserIdentity:
        if not session_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        try:
            return auth_service.verify_session_token(session_token)
        except AuthTokenError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session",
            ) from error

    def current_identity(
        session_token: str | None = Cookie(
            default=None,
            alias=resolved_settings.auth_cookie_name,
        ),
        x_demo_user: str | None = Header(default=None),
    ) -> UserIdentity:
        if session_token:
            try:
                return auth_service.verify_session_token(session_token)
            except AuthTokenError as error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired session",
                ) from error
        if resolved_settings.auth_required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        fallback_user = x_demo_user or resolved_settings.default_user_id
        if not USER_ID_PATTERN.fullmatch(fallback_user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid demo user id",
            )
        return UserIdentity(
            user_id=fallback_user,
            display_name="演示用户",
            source="demo-header",
        )

    def current_user(identity: UserIdentity = Depends(current_identity)) -> str:
        return identity.user_id

    def set_session_cookie(response: Response, identity: UserIdentity) -> None:
        response.set_cookie(
            key=resolved_settings.auth_cookie_name,
            value=auth_service.issue_session_token(identity),
            max_age=resolved_settings.auth_session_ttl_seconds,
            httponly=True,
            secure=resolved_settings.auth_cookie_secure,
            samesite="lax",
            path="/",
        )

    async def owned_conversation(conversation_id: str, user_id: str) -> None:
        try:
            await repository.require_conversation(conversation_id, user_id)
        except ConversationNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found") from error

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "agent-support-api",
            "model_provider": resolved_model_gateway.provider_name,
            "model": resolved_model_gateway.model_name,
        }

    @app.get("/api/v1/auth/me", response_model=AuthUserDTO)
    async def auth_me(identity: UserIdentity = Depends(session_identity)) -> AuthUserDTO:
        return AuthUserDTO(
            user_id=identity.user_id,
            display_name=identity.display_name,
            source=identity.source,
        )

    @app.post("/api/v1/auth/exchange", response_model=AuthUserDTO)
    async def exchange_launch_token(
        payload: ExchangeLaunchTokenRequest,
        response: Response,
    ) -> AuthUserDTO:
        try:
            launch_identity = auth_service.verify_launch_token(payload.launch_token)
        except AuthTokenError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired launch token",
            ) from error
        identity = UserIdentity(
            user_id=launch_identity.user_id,
            display_name=launch_identity.display_name,
            source="launch",
        )
        set_session_cookie(response, identity)
        return AuthUserDTO(
            user_id=identity.user_id,
            display_name=identity.display_name,
            source=identity.source,
        )

    @app.post("/api/v1/auth/demo-session", response_model=AuthUserDTO)
    async def create_demo_session(
        payload: DemoSessionRequest,
        response: Response,
    ) -> AuthUserDTO:
        if resolved_settings.environment.lower() == "production":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Demo authentication is disabled",
            )
        display_names = {
            "demo-user": "演示用户",
            "demo-return-user": "还伞场景用户",
            "demo-billing-user": "计费场景用户",
            "demo-nearby-user": "附近网点场景用户",
        }
        identity = UserIdentity(
            user_id=f"{payload.profile}~{payload.client_id}",
            display_name=display_names[payload.profile],
            source="demo",
        )
        set_session_cookie(response, identity)
        return AuthUserDTO(
            user_id=identity.user_id,
            display_name=identity.display_name,
            source=identity.source,
        )

    @app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(response: Response) -> None:
        response.delete_cookie(
            key=resolved_settings.auth_cookie_name,
            path="/",
            secure=resolved_settings.auth_cookie_secure,
            httponly=True,
            samesite="lax",
        )

    @app.get("/api/v1/conversations", response_model=list[ConversationDTO])
    async def list_conversations(user_id: str = Depends(current_user)) -> list[ConversationDTO]:
        return await repository.list_conversations(user_id)

    @app.post("/api/v1/conversations", response_model=ConversationDTO, status_code=status.HTTP_201_CREATED)
    async def create_conversation(
        payload: CreateConversationRequest,
        user_id: str = Depends(current_user),
    ) -> ConversationDTO:
        return await repository.create_conversation(user_id, payload.title)

    @app.get("/api/v1/memories", response_model=list[UserMemoryDTO])
    async def list_memories(user_id: str = Depends(current_user)) -> list[UserMemoryDTO]:
        memories = await memory_repository.list_user_memories(
            user_id,
            limit=resolved_settings.memory_max_long_term_items,
        )
        return [
            UserMemoryDTO(
                key=memory.key,
                label=MEMORY_LABELS[memory.key],
                value=memory.value,
                updated_at=memory.updated_at,
            )
            for memory in memories
        ]

    @app.delete("/api/v1/memories", response_model=DeleteMemoriesResponse)
    async def delete_memories(user_id: str = Depends(current_user)) -> DeleteMemoriesResponse:
        deleted = await memory_repository.delete_user_memories(user_id)
        return DeleteMemoriesResponse(deleted=deleted)

    @app.get("/api/v1/observability/summary", response_model=TraceSummaryDTO)
    async def observability_summary(
        user_id: str = Depends(current_user),
    ) -> TraceSummaryDTO:
        summary = await trace_repository.summary(user_id)
        return TraceSummaryDTO.model_validate(summary)

    @app.get("/api/v1/observability/traces", response_model=list[TurnTraceDTO])
    async def list_traces(
        limit: int = Query(default=20, ge=1, le=100),
        user_id: str = Depends(current_user),
    ) -> list[TurnTraceDTO]:
        traces = await trace_repository.list_traces(user_id, limit)
        return [TurnTraceDTO.model_validate(trace) for trace in traces]

    @app.get("/api/v1/observability/traces/{trace_id}", response_model=TraceDetailDTO)
    async def trace_detail(
        trace_id: str,
        user_id: str = Depends(current_user),
    ) -> TraceDetailDTO:
        detail = await trace_repository.get_detail(trace_id, user_id)
        if detail is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
        return TraceDetailDTO(
            trace=TurnTraceDTO.model_validate(detail.trace),
            tool_spans=[ToolSpanDTO.model_validate(span) for span in detail.tool_spans],
            model_spans=[ModelSpanDTO.model_validate(span) for span in detail.model_spans],
        )

    @app.get("/api/v1/conversations/{conversation_id}/messages", response_model=list[MessageDTO])
    async def list_messages(
        conversation_id: str,
        user_id: str = Depends(current_user),
    ) -> list[MessageDTO]:
        await owned_conversation(conversation_id, user_id)
        return await repository.list_messages(conversation_id, user_id)

    @app.post("/api/v1/conversations/{conversation_id}/messages:stream")
    async def stream_message(
        conversation_id: str,
        payload: SendMessageRequest,
        request: Request,
        user_id: str = Depends(current_user),
    ) -> StreamingResponse:
        await owned_conversation(conversation_id, user_id)

        async def event_source() -> AsyncIterator[str]:
            async for event in stream_support_reply(
                repository=repository,
                agent_runner=agent_runner,
                model_gateway=resolved_model_gateway,
                memory_service=memory_service,
                trace_service=trace_service,
                user_id=user_id,
                conversation_id=conversation_id,
                content=payload.content.strip(),
                request_id=payload.request_id,
                character_delay=resolved_settings.stream_character_delay,
            ):
                if await request.is_disconnected():
                    break
                yield event

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app()
