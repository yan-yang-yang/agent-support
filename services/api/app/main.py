from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .agent.runner import AgentRunner
from .business import BusinessGateway, HttpUmbrellaBusinessGateway
from .config import Settings
from .model_gateway.factory import create_model_gateway
from .model_gateway.protocol import ModelGateway
from .model_gateway.repository import ModelCallRepository
from .repository import ConversationNotFoundError, SQLiteConversationRepository
from .schemas import ConversationDTO, CreateConversationRequest, MessageDTO, SendMessageRequest
from .sse import stream_support_reply
from .tools.executor import ToolExecutor
from .tools.repository import ToolCallRepository


def create_app(
    settings: Settings | None = None,
    business_gateway: BusinessGateway | None = None,
    model_gateway: ModelGateway | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_environment()
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

    app = FastAPI(title="Agent Support API", version="0.1.0", lifespan=lifespan)
    app.state.repository = repository
    app.state.settings = resolved_settings
    app.state.business_gateway = resolved_business_gateway
    app.state.model_gateway = resolved_model_gateway
    app.state.model_call_repository = model_call_repository
    app.state.tool_call_repository = tool_call_repository
    app.state.agent_runner = agent_runner
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Demo-User", "X-Request-ID"],
    )

    def current_user(x_demo_user: str | None = Header(default=None)) -> str:
        return x_demo_user or resolved_settings.default_user_id

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

    @app.get("/api/v1/conversations", response_model=list[ConversationDTO])
    async def list_conversations(user_id: str = Depends(current_user)) -> list[ConversationDTO]:
        return await repository.list_conversations(user_id)

    @app.post("/api/v1/conversations", response_model=ConversationDTO, status_code=status.HTTP_201_CREATED)
    async def create_conversation(
        payload: CreateConversationRequest,
        user_id: str = Depends(current_user),
    ) -> ConversationDTO:
        return await repository.create_conversation(user_id, payload.title)

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
