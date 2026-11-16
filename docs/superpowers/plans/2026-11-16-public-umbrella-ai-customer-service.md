# Public Umbrella AI Customer Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a locally runnable mobile H5 AI customer-service demo for public-umbrella users that handles return failures, billing disputes, and nearby-station searches with persistent conversations and controlled agent memory.

**Architecture:** Use a React H5 behind Nginx, a modular FastAPI customer-service API, and a separate FastAPI mock umbrella-business service. LangGraph orchestrates the agent; PostgreSQL stores source-of-truth data, Redis supports rate limiting/idempotency/stream state, and adapters isolate OpenAI and umbrella-business APIs.

**Tech Stack:** React, TypeScript, Vite, shadcn/ui, Tailwind CSS, Zustand, TanStack Query, Vitest, Playwright, Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL, Redis, LangGraph, OpenAI SDK, httpx, pytest, Nginx, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-16-umbrella-ai-customer-service-design.md`

## Global Constraints

- Phase 1 supports AI-only customer service; no live human-agent console, queue, assignment, takeover, or WebSocket agent channel.
- Do not add RAG, embeddings, a vector database, document chunking, or knowledge-base retrieval.
- The H5 receives only a signed current-user identity; it must not require an order ID in the entry URL.
- The three required scenarios are return failure, billing dispute, and nearby-station search.
- All original messages and tool events are persisted; summaries never replace or delete source messages.
- Model context uses valid long-term memories, a rolling summary, and recent messages instead of unbounded full history.
- The only Phase 1 business write is creation of a mock support ticket; the agent must not mutate orders, billing, refunds, or devices.
- OpenAI is the first provider, but agent code may depend only on the OpenAI-compatible `ModelGateway` interface.
- PostgreSQL is the source of truth; Redis must never be the only store for conversations or messages.
- The complete environment starts locally with `docker compose up --build` after `.env` is configured.
- Never add resumes, personal documents, API keys, `.env`, production user data, or generated runtime data to Git.
- Build the UI mobile-first for WeChat H5, including safe areas, virtual-keyboard behavior, touch targets, streaming reconnects, and cursor-paginated history.

## Review Focus

- A retried or reconnected send must not duplicate the user message, assistant turn, tool call, or support ticket. Pinned by Task 13.
- A model that repeatedly requests tools must stop at the configured loop limit and produce a safe fallback. Pinned by Task 9.
- A timed-out or malformed umbrella-business response must never be presented as a successful order, billing, or device action. Pinned by Task 7.
- Context compression must reduce model input while preserving every original message for history display. Pinned by Task 8.
- One signed-in user must never read, stream to, or modify another user's conversation. Pinned by Tasks 4 and 13.

---

## Planned File Structure

```text
agent-support/
├── apps/web/
│   ├── src/api/                 # HTTP/SSE client and wire DTOs
│   ├── src/app/                 # router, providers, global app shell
│   ├── src/components/chat/     # chat-specific mobile UI
│   ├── src/components/ui/       # shadcn/ui primitives
│   ├── src/features/session/    # current-user bootstrap
│   ├── src/features/chat/       # conversation queries and stream state
│   └── src/test/                # Vitest setup and fixtures
├── services/api/
│   ├── app/core/                # config, errors, logging, request context
│   ├── app/identity/            # demo token issue/verification
│   ├── app/conversation/        # conversations, messages, persistence
│   ├── app/model_gateway/       # provider-neutral model interface/adapters
│   ├── app/business/            # umbrella gateway, tools, risk policy
│   ├── app/context/             # context budget, summaries, memories
│   ├── app/agent/               # LangGraph state, nodes, scenarios, runner
│   ├── app/streaming/           # SSE event contract and endpoint
│   ├── app/db/                  # SQLAlchemy session and models
│   ├── alembic/                 # database migrations
│   └── tests/                   # unit and API integration tests
├── services/mock-business/
│   ├── app/                     # seeded public-umbrella API
│   └── tests/                   # deterministic scenario tests
├── infra/nginx/                 # H5/API gateway configuration
├── tests/e2e/                   # Docker-backed Playwright flows
├── docker-compose.yml
├── .env.example
└── README.md
```

### Task 1: FastAPI Service Foundation

**Files:**
- Create: `pyproject.toml`
- Create: `services/api/pyproject.toml`
- Create: `services/api/app/__init__.py`
- Create: `services/api/app/core/config.py`
- Create: `services/api/app/core/errors.py`
- Create: `services/api/app/main.py`
- Create: `services/api/tests/conftest.py`
- Create: `services/api/tests/test_health.py`

**Interfaces:**
- Produces: `Settings(BaseSettings)`, `create_app(settings: Settings | None = None) -> FastAPI`, `GET /health/live`, and `GET /health/ready`.

- [ ] **Step 1: Write the failing API health tests**

```python
def test_live_health_returns_service_name_and_ok(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "customer-service-api"}

def test_ready_health_reports_dependency_state(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
```

- [ ] **Step 2: Run `uv run --project services/api pytest services/api/tests/test_health.py -v` and verify it fails because the application package does not exist**

- [ ] **Step 3: Add the uv workspace and the API package dependencies**

Create the root workspace and `services/api/pyproject.toml` with Python 3.12+, FastAPI, Uvicorn, Pydantic Settings, pytest, pytest-asyncio, and httpx.

- [ ] **Step 4: Implement `Settings` and `create_app` with live/ready routers**

`Settings` must read environment variables with an `APP_` prefix and expose `app_name`, `environment`, `database_url`, and `redis_url`.

Create a test `client` fixture that injects successful readiness probes; later persistence tasks replace those probes with real dependency checks.

- [ ] **Step 5: Run `uv lock && uv run --project services/api pytest services/api/tests/test_health.py -v` and verify both tests pass**

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock services/api
git commit -m "build: bootstrap customer service API"
```

### Task 2: Deterministic Mock Umbrella Business API

**Files:**
- Modify: `pyproject.toml`
- Create: `services/mock-business/pyproject.toml`
- Create: `services/mock-business/app/main.py`
- Create: `services/mock-business/app/models.py`
- Create: `services/mock-business/app/store.py`
- Create: `services/mock-business/app/routes.py`
- Create: `services/mock-business/app/seed.json`
- Create: `services/mock-business/tests/conftest.py`
- Create: `services/mock-business/tests/test_scenarios.py`

**Interfaces:**
- Produces: `GET /v1/users/{user_id}/active-rental`, `GET /v1/users/{user_id}/orders`, `GET /v1/orders/{order_id}/billing`, `GET /v1/stations/{station_id}`, `GET /v1/stations/nearby`, and `POST /v1/support-tickets`.
- Produces fixed IDs `demo-return-user`, `demo-billing-user`, and `demo-nearby-user` with repeatable scenario data.

- [ ] **Step 1: Write failing tests for the three seeded scenarios and ticket creation**

```python
def test_return_user_has_active_rental_with_station_fault(client):
    rental = client.get("/v1/users/demo-return-user/active-rental").json()
    station = client.get(f"/v1/stations/{rental['station_id']}").json()
    assert rental["status"] == "active"
    assert station["online"] is True
    assert station["available_docks"] == 0

def test_billing_user_has_explainable_line_items(client):
    order = client.get("/v1/users/demo-billing-user/orders").json()[0]
    billing = client.get(f"/v1/orders/{order['id']}/billing").json()
    assert billing["total_amount"] == sum(item["amount"] for item in billing["items"])

def test_nearby_search_filters_for_return_capacity(client):
    stations = client.get("/v1/stations/nearby?lat=30.2741&lng=120.1551&purpose=return").json()
    assert stations
    assert all(station["available_docks"] > 0 for station in stations)
```

- [ ] **Step 2: Run `uv run --project services/mock-business pytest services/mock-business/tests/test_scenarios.py -v` and verify import or route failures**

- [ ] **Step 3: Define Pydantic wire models for rentals, orders, billing, stations, and support tickets**

- [ ] **Step 4: Implement `SeedStore` to load `seed.json` and expose deterministic query methods**

The store must return copies, generate stable ticket IDs from an idempotency key, and never mutate seeded orders or billing.

- [ ] **Step 5: Implement the versioned routes and internal-token dependency**

All `/v1` routes require `X-Internal-Token`; the test `client` fixture injects the configured test token on every request.

- [ ] **Step 6: Run the mock-service tests and verify they pass**

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock services/mock-business
git commit -m "feat: add deterministic umbrella business API"
```

### Task 3: Demo Identity and Request Context

**Files:**
- Modify: `services/api/app/core/config.py`
- Create: `services/api/app/core/request_context.py`
- Create: `services/api/app/identity/models.py`
- Create: `services/api/app/identity/token_service.py`
- Create: `services/api/app/identity/routes.py`
- Create: `services/api/tests/identity/test_tokens.py`
- Create: `services/api/tests/identity/test_routes.py`

**Interfaces:**
- Produces: `RequestContext(user_id: str, request_id: str)`.
- Produces: `DemoTokenService.issue(user_id: str, expires_in: timedelta) -> str` and `DemoTokenService.verify(token: str) -> RequestContext`.
- Produces: `POST /api/v1/demo/session` and `get_request_context(authorization, x_request_id) -> RequestContext`.

- [ ] **Step 1: Write failing tests for valid, expired, and tampered tokens**

```python
def test_token_round_trip(token_service):
    token = token_service.issue("demo-return-user", timedelta(minutes=15))
    assert token_service.verify(token).user_id == "demo-return-user"

@pytest.mark.parametrize("case", ["expired", "tampered"])
def test_invalid_token_is_rejected(case, token_factory, token_service):
    with pytest.raises(InvalidIdentityToken):
        token_service.verify(token_factory(case))
```

- [ ] **Step 2: Run the identity tests and verify they fail because `DemoTokenService` is missing**

- [ ] **Step 3: Implement signed short-lived tokens and `RequestContext`**

Use a server-side `DEMO_TOKEN_SECRET`; never accept a user ID directly from a protected endpoint.

- [ ] **Step 4: Implement the demo-session route and bearer-token dependency**

The route accepts only one of the three configured demo user IDs and returns `access_token`, `expires_at`, and `user`.

- [ ] **Step 5: Run all identity tests and verify they pass**

- [ ] **Step 6: Commit**

```bash
git add services/api/app/core services/api/app/identity services/api/tests/identity
git commit -m "feat: add signed demo user identity"
```

### Task 4: Conversation and Full Message Persistence

**Files:**
- Modify: `services/api/pyproject.toml`
- Create: `services/api/alembic.ini`
- Create: `services/api/alembic/env.py`
- Create: `services/api/alembic/versions/0001_conversations.py`
- Create: `services/api/app/db/base.py`
- Create: `services/api/app/db/seed.py`
- Create: `services/api/app/db/session.py`
- Create: `services/api/app/conversation/models.py`
- Create: `services/api/app/conversation/schemas.py`
- Create: `services/api/app/conversation/repository.py`
- Create: `services/api/app/conversation/service.py`
- Create: `services/api/app/conversation/routes.py`
- Create: `services/api/tests/conversation/test_service.py`
- Create: `services/api/tests/conversation/test_routes.py`
- Modify: `services/api/tests/conftest.py`

**Interfaces:**
- Consumes: `RequestContext` from Task 3.
- Produces: `ConversationService.create(user_id: str) -> ConversationDTO`.
- Produces: `ConversationService.append_message(conversation_id: UUID, user_id: str, role: MessageRole, content: MessageContent, idempotency_key: str) -> MessageDTO`.
- Produces: `ConversationService.list_messages(conversation_id: UUID, user_id: str, before: UUID | None, limit: int) -> CursorPage[MessageDTO]`.
- Produces protected conversation create/list, cursor-paginated message, and `POST /api/v1/messages/{id}/feedback` endpoints.

- [ ] **Step 1: Write failing service tests for persistence, idempotency, pagination, and ownership**

```python
async def test_original_messages_survive_reload(service, new_service):
    conversation = await service.create("demo-return-user")
    await service.append_message(conversation.id, "demo-return-user", "user", {"text": "还不了伞"}, "m-1")
    page = await new_service.list_messages(conversation.id, "demo-return-user", None, 20)
    assert [message.content["text"] for message in page.items] == ["还不了伞"]

async def test_other_user_cannot_read_conversation(service, conversation):
    with pytest.raises(ConversationNotFound):
        await service.list_messages(conversation.id, "demo-billing-user", None, 20)
```

- [ ] **Step 2: Run the conversation tests and verify missing-model failures**

- [ ] **Step 3: Add SQLAlchemy, Alembic, asyncpg, and testcontainers dependencies and create the initial migration**

The migration creates `users`, `conversations`, `messages`, and `message_feedback`; `conversations` includes `service_mode`, `handoff_status`, and nullable `assigned_agent_id`.

- [ ] **Step 4: Implement repositories and `ConversationService` with ownership hidden as not-found**

Use a unique constraint on `(conversation_id, idempotency_key)` and keyset pagination by `(created_at, id)`.

- [ ] **Step 5: Implement protected routes and bootstrap enrichment**

`seed.py` idempotently inserts the three demo users. `GET /api/v1/bootstrap` returns the current demo user, latest conversation, and three quick actions. Feedback writes enforce message ownership and one current rating per user/message.

- [ ] **Step 6: Extend the test fixture to start PostgreSQL, run migrations, seed users, and then run the conversation tests**

- [ ] **Step 7: Commit**

```bash
git add services/api
git commit -m "feat: persist conversations and complete message history"
```

### Task 5: Mobile React H5 Shell

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/tailwind.config.ts`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/app/App.tsx`
- Create: `apps/web/src/app/providers.tsx`
- Create: `apps/web/src/styles/globals.css`
- Create: `apps/web/src/components/chat/ChatHeader.tsx`
- Create: `apps/web/src/components/chat/ChatComposer.tsx`
- Create: `apps/web/src/components/chat/QuickActions.tsx`
- Create: `apps/web/src/app/App.test.tsx`
- Create: `apps/web/src/test/setup.ts`

**Interfaces:**
- Produces: `/chat` mobile route, `ChatComposer({disabled, onSend})`, and `QuickActions({onSelect})`.
- Produces CSS tokens for H5 safe areas and a maximum chat-shell width of 430px.

- [ ] **Step 1: Write a failing UI test for the mobile shell and quick actions**

```tsx
it("shows the three supported entry actions and sends typed text", async () => {
  render(<App />)
  expect(screen.getByRole("button", { name: "还伞失败" })).toBeVisible()
  expect(screen.getByRole("button", { name: "计费问题" })).toBeVisible()
  expect(screen.getByRole("button", { name: "附近网点" })).toBeVisible()
  await user.type(screen.getByRole("textbox"), "我还不了伞")
  await user.click(screen.getByRole("button", { name: "发送" }))
  expect(screen.getByText("我还不了伞")).toBeVisible()
})
```

- [ ] **Step 2: Run `npm --prefix apps/web test -- --run src/app/App.test.tsx` and verify the app is missing**

- [ ] **Step 3: Add React/Vite, Tailwind, shadcn/ui prerequisites, TanStack Query, Zustand, Vitest, and Testing Library**

- [ ] **Step 4: Implement the provider shell, chat header, quick actions, and keyboard-safe composer**

Use shadcn/ui primitives only for general controls; keep chat components owned by this project.

- [ ] **Step 5: Run the UI test and `npm --prefix apps/web run build` and verify both pass**

- [ ] **Step 6: Commit**

```bash
git add apps/web
git commit -m "feat: add mobile customer chat shell"
```

### Task 6: OpenAI-Compatible Model Gateway

**Files:**
- Modify: `services/api/app/core/config.py`
- Create: `services/api/alembic/versions/0002_model_calls.py`
- Create: `services/api/app/model_gateway/types.py`
- Create: `services/api/app/model_gateway/protocol.py`
- Create: `services/api/app/model_gateway/openai_adapter.py`
- Create: `services/api/app/model_gateway/fake_adapter.py`
- Create: `services/api/app/model_gateway/factory.py`
- Create: `services/api/app/model_gateway/repository.py`
- Create: `services/api/tests/model_gateway/test_openai_adapter.py`
- Create: `services/api/tests/model_gateway/test_fake_adapter.py`

**Interfaces:**
- Produces: `ModelGateway.stream_chat(request: ModelRequest) -> AsyncIterator[ModelEvent]`.
- Produces: `ModelGateway.complete_structured(request: ModelRequest, schema: type[T]) -> T`.
- Produces normalized `TextDelta`, `ToolCallDelta`, `Usage`, `Completed`, and `ModelError` events.
- Produces: `ModelCallRepository.start(...) -> ModelCallDTO` and `ModelCallRepository.complete(call_id, usage, status, error_code) -> None`.

- [ ] **Step 1: Write failing adapter contract tests**

```python
async def test_stream_normalizes_text_tool_and_usage_events(gateway, provider_stream):
    events = [event async for event in gateway.stream_chat(ModelRequest(messages=[], tools=[]))]
    assert [event.kind for event in events] == ["text_delta", "tool_call_delta", "usage", "completed"]

async def test_provider_timeout_becomes_retryable_model_error(gateway):
    with pytest.raises(ModelGatewayError, match="timeout") as error:
        await collect(gateway.stream_chat(ModelRequest(messages=[], tools=[])))
    assert error.value.retryable is True
```

- [ ] **Step 2: Run the model-gateway tests and verify missing-protocol failures**

- [ ] **Step 3: Define provider-neutral request, tool, structured-output, and event types**

- [ ] **Step 4: Add the `model_calls` migration and repository for model, token, latency, status, and correlation fields**

- [ ] **Step 5: Implement `OpenAIAdapter` with timeout, bounded retry, cancellation, streaming normalization, and repository-backed usage logging**

- [ ] **Step 6: Implement deterministic `FakeModelGateway` scripts for unit and end-to-end tests**

- [ ] **Step 7: Implement the environment-driven gateway factory**

`MODEL_PROVIDER=openai` creates `OpenAIAdapter`; `MODEL_PROVIDER=fake` is allowed only outside production.

- [ ] **Step 8: Run all model-gateway tests and verify they pass**

- [ ] **Step 9: Commit**

```bash
git add services/api/app/model_gateway services/api/app/core/config.py services/api/tests/model_gateway
git commit -m "feat: add OpenAI-compatible model gateway"
```

### Task 7: Umbrella Business Adapter and Safe Tool Executor

**Files:**
- Create: `services/api/alembic/versions/0003_tool_calls_and_tickets.py`
- Create: `services/api/app/business/types.py`
- Create: `services/api/app/business/gateway.py`
- Create: `services/api/app/business/http_adapter.py`
- Create: `services/api/app/business/tool_definitions.py`
- Create: `services/api/app/business/tool_executor.py`
- Create: `services/api/app/business/tool_repository.py`
- Create: `services/api/app/business/risk_policy.py`
- Create: `services/api/app/ticket/models.py`
- Create: `services/api/app/ticket/repository.py`
- Create: `services/api/app/ticket/service.py`
- Create: `services/api/tests/business/test_http_adapter.py`
- Create: `services/api/tests/business/test_tool_executor.py`
- Create: `services/api/tests/ticket/test_ticket_service.py`

**Interfaces:**
- Consumes: Mock API endpoints from Task 2.
- Produces: `UmbrellaBusinessGateway` methods matching the six stable tools in the design spec.
- Produces: `ToolExecutor.execute(name: ToolName, arguments: dict[str, object], context: ToolContext) -> ToolResult`.
- Produces: `TicketService.create_from_tool_result(user_id: str, conversation_id: UUID, idempotency_key: str, result: ToolResult) -> SupportTicketDTO`.
- Produces: protected `GET /api/v1/tickets/{ticket_id}` that hides non-owned tickets as not-found.
- Produces only these tool names: `get_active_rental`, `list_recent_orders`, `get_order_billing`, `get_station_status`, `find_nearby_stations`, `create_support_ticket`.

- [ ] **Step 1: Write failing adapter tests for mapping, timeout, malformed responses, and internal errors**

```python
async def test_malformed_billing_response_is_not_returned_as_success(adapter):
    with pytest.raises(BusinessGatewayError) as error:
        await adapter.get_order_billing("bad-order")
    assert error.value.safe_code == "UPSTREAM_INVALID_RESPONSE"

async def test_timeout_is_retryable_but_never_claims_success(executor):
    result = await executor.execute("get_station_status", {"station_id": "slow"}, tool_context())
    assert result.status == "error"
    assert result.retryable is True
    assert result.data is None
```

- [ ] **Step 2: Run the business tests and verify they fail on missing interfaces**

- [ ] **Step 3: Define internal domain DTOs and the `UmbrellaBusinessGateway` protocol**

- [ ] **Step 4: Implement the httpx adapter with internal authentication, strict Pydantic response validation, request IDs, and timeouts**

- [ ] **Step 5: Add `tool_calls` and `support_tickets` tables plus their repositories**

Tool calls store parameter/result summaries, timing, status, and error codes. Local support tickets mirror the stable external ticket ID and enforce a unique idempotency key.

- [ ] **Step 6: Implement the whitelist-only `ToolExecutor`, `RiskPolicy`, and repository audit writes**

Reject unknown tools, extra arguments, user-ID overrides, and every write except idempotent `create_support_ticket`.

- [ ] **Step 7: Implement `TicketService` plus the protected ticket-status route, and test idempotency and ownership**

- [ ] **Step 8: Run all business adapter, tool executor, and ticket tests and verify they pass**

- [ ] **Step 9: Commit**

```bash
git add services/api/alembic services/api/app/business services/api/app/ticket services/api/tests/business services/api/tests/ticket
git commit -m "feat: add safe umbrella business tools"
```

### Task 8: Context Compression and Controlled Long-Term Memory

**Files:**
- Create: `services/api/alembic/versions/0004_agent_memory.py`
- Create: `services/api/app/context/models.py`
- Create: `services/api/app/context/repository.py`
- Create: `services/api/app/context/token_budget.py`
- Create: `services/api/app/context/assembler.py`
- Create: `services/api/app/context/summarizer.py`
- Create: `services/api/app/context/memory_service.py`
- Create: `services/api/tests/context/test_assembler.py`
- Create: `services/api/tests/context/test_summarizer.py`
- Create: `services/api/tests/context/test_memory_service.py`

**Interfaces:**
- Consumes: conversation messages from Task 4 and structured completion from Task 6.
- Produces: `ContextAssembler.build(user_id: str, conversation_id: UUID, current_message: MessageDTO, budget: TokenBudget) -> ModelContext`.
- Produces: `SummaryService.maybe_summarize(conversation_id: UUID) -> ConversationSummaryDTO | None`.
- Produces: `UserMemoryService.propose_and_store(user_id: str, conversation_id: UUID) -> list[UserMemoryDTO]`.
- Produces: `AgentStateRepository.load(conversation_id: UUID) -> AgentStateSnapshot | None` and `AgentStateRepository.save(conversation_id: UUID, version: int, state: dict[str, object]) -> AgentStateSnapshot`.

- [ ] **Step 1: Write failing tests for bounded context, source-history preservation, and memory rejection**

```python
async def test_old_turns_are_summarized_but_original_messages_remain(services, long_conversation):
    context = await services.assembler.build(
        long_conversation.user_id,
        long_conversation.id,
        long_conversation.current_message,
        budget=TokenBudget(max_tokens=6000),
    )
    assert context.summary is not None
    assert len(context.recent_messages) <= 15
    assert await services.conversations.count_messages(long_conversation.id) == long_conversation.original_count

@pytest.mark.parametrize("candidate", ["模型猜测用户生气", "银行卡号 6222...", "完整对话复制"])
async def test_unsafe_memory_candidate_is_rejected(memory_service, candidate):
    assert await memory_service.validate_candidate(candidate) is False
```

- [ ] **Step 2: Run the context tests and verify missing-service failures**

- [ ] **Step 3: Add tables for conversation states, summaries, and user memories**

Summaries store covered message boundaries and version; memories store type, structured content, source conversation, confidence, expiry, and status.

- [ ] **Step 4: Implement token estimation and the fixed context ordering**

The output order is system rules, user profile, valid memories, current summary, at most 15 recent messages, and the current user message.

- [ ] **Step 5: Implement rolling summary generation at 20 turns or the configured token threshold**

- [ ] **Step 6: Implement versioned agent-state snapshots plus memory candidate validation, expiry, and persistence**

Allow only support-relevant types: `recurring_issue`, `open_ticket`, and `preferred_station`; reject raw transcripts and sensitive payment data.

- [ ] **Step 7: Run all context and memory tests and verify they pass**

- [ ] **Step 8: Commit**

```bash
git add services/api/alembic services/api/app/context services/api/tests/context
git commit -m "feat: add bounded context and agent memory"
```

### Task 9: LangGraph Runtime, Routing, and Loop Safety

**Files:**
- Create: `services/api/app/agent/state.py`
- Create: `services/api/app/agent/events.py`
- Create: `services/api/app/agent/router.py`
- Create: `services/api/app/agent/graph.py`
- Create: `services/api/app/agent/runner.py`
- Create: `services/api/app/agent/nodes/common.py`
- Create: `services/api/tests/agent/test_router.py`
- Create: `services/api/tests/agent/test_graph_safety.py`

**Interfaces:**
- Consumes: `ModelGateway`, `ToolExecutor`, `ContextAssembler`, `AgentStateRepository`, and `ConversationService`.
- Produces: `AgentState` with the fields fixed in the design spec.
- Produces: `AgentRunner.stream_turn(context: RequestContext, conversation_id: UUID, message: MessageDTO) -> AsyncIterator[AgentEvent]`.
- Produces scenario values `return_failure`, `billing_dispute`, `nearby_station`, and `unknown`.

- [ ] **Step 1: Write failing routing and loop-limit tests**

```python
@pytest.mark.parametrize(("text", "scenario"), [
    ("伞插回去了还在计费", "return_failure"),
    ("为什么扣了我两次钱", "billing_dispute"),
    ("附近哪里能还伞", "nearby_station"),
])
async def test_routes_supported_scenarios(runner, text, scenario):
    result = await collect_state(runner, text)
    assert result.scenario == scenario

async def test_tool_loop_stops_at_configured_limit(looping_model, runner):
    events = [event async for event in runner.stream_turn_for_test(looping_model)]
    assert count(events, "tool.started") == runner.max_tool_calls
    assert events[-1].kind == "safe_fallback"
```

- [ ] **Step 2: Run the agent tests and verify missing-graph failures**

- [ ] **Step 3: Define serializable `AgentState` and the provider-neutral `AgentEvent` union**

- [ ] **Step 4: Implement deterministic pre-routing with model-assisted fallback**

Clear supported phrases may route deterministically; ambiguous input uses structured model classification.

- [ ] **Step 5: Build the common LangGraph nodes, persist versioned state snapshots, and enforce maximum node/tool iterations**

- [ ] **Step 6: Implement `safe_fallback` for unknown intent, model failure, tool failure, and loop exhaustion**

- [ ] **Step 7: Run all routing and graph-safety tests and verify they pass**

- [ ] **Step 8: Commit**

```bash
git add services/api/app/agent services/api/tests/agent
git commit -m "feat: add safe LangGraph customer service runtime"
```

### Task 10: Return-Failure Scenario

**Files:**
- Create: `services/api/app/agent/scenarios/return_failure.py`
- Create: `services/api/tests/agent/test_return_failure.py`
- Modify: `services/api/app/agent/graph.py`

**Interfaces:**
- Consumes: `AgentState`, `get_active_rental`, `list_recent_orders`, `get_station_status`, `find_nearby_stations`, `create_support_ticket`, and `TicketService`.
- Produces: `build_return_failure_subgraph() -> CompiledStateGraph`.

- [ ] **Step 1: Write failing tests for active rental, full station, no active rental, and unresolved-ticket paths**

```python
async def test_full_station_recommends_return_capacity_without_ending_order(return_runner):
    result = await return_runner.run("伞插不进去")
    assert result.state.active_rental_id is not None
    assert result.cards[0].type == "nearby_stations"
    assert "结束订单" not in result.executed_tools

async def test_unresolved_return_failure_creates_one_idempotent_ticket(return_runner):
    first = await return_runner.run("还是还不了")
    second = await return_runner.retry_same_turn()
    assert first.ticket.id == second.ticket.id
```

- [ ] **Step 2: Run the scenario tests and verify the graph has no return-failure branch**

- [ ] **Step 3: Implement active-rental lookup, missing-location collection, station diagnosis, nearby recommendation, and ticket fallback nodes**

- [ ] **Step 4: Register the subgraph without adding order-ending or billing-mutation tools**

- [ ] **Step 5: Run the return-failure tests and full agent test suite**

- [ ] **Step 6: Commit**

```bash
git add services/api/app/agent services/api/tests/agent/test_return_failure.py
git commit -m "feat: handle umbrella return failures"
```

### Task 11: Billing-Dispute Scenario

**Files:**
- Create: `services/api/app/agent/scenarios/billing_dispute.py`
- Create: `services/api/tests/agent/test_billing_dispute.py`
- Modify: `services/api/app/agent/graph.py`

**Interfaces:**
- Consumes: `list_recent_orders`, `get_order_billing`, `create_support_ticket`, and `TicketService`.
- Produces: `build_billing_dispute_subgraph() -> CompiledStateGraph` and a structured billing card whose amount values come only from tool results.

- [ ] **Step 1: Write failing tests for order selection, verified totals, unexplained differences, and no-refund enforcement**

```python
async def test_billing_amounts_are_copied_from_tool_result(billing_runner):
    result = await billing_runner.run("这个订单为什么扣了12元")
    assert result.card.total_amount == Decimal("12.00")
    assert result.card.line_items == result.tool_results["get_order_billing"].items

async def test_dispute_creates_ticket_but_never_refunds(billing_runner):
    result = await billing_runner.run("费用不对，给我退款")
    assert result.ticket.category == "billing_dispute"
    assert "refund" not in result.executed_tools
```

- [ ] **Step 2: Run the billing tests and verify the scenario is missing**

- [ ] **Step 3: Implement recent-order selection and billing-detail retrieval**

- [ ] **Step 4: Implement deterministic amount-card construction and unresolved-dispute ticket creation**

- [ ] **Step 5: Register the subgraph and run the billing plus complete agent suites**

- [ ] **Step 6: Commit**

```bash
git add services/api/app/agent services/api/tests/agent/test_billing_dispute.py
git commit -m "feat: handle billing disputes safely"
```

### Task 12: Nearby-Station Scenario

**Files:**
- Create: `services/api/app/agent/scenarios/nearby_station.py`
- Create: `services/api/tests/agent/test_nearby_station.py`
- Modify: `services/api/app/agent/graph.py`

**Interfaces:**
- Consumes: `find_nearby_stations`.
- Produces: `build_nearby_station_subgraph() -> CompiledStateGraph` and station cards sorted for borrow or return intent.

- [ ] **Step 1: Write failing tests for missing location, borrow/return filtering, sorting, and stale inventory wording**

```python
async def test_missing_location_requests_location_without_calling_tool(station_runner):
    result = await station_runner.run("附近哪里可以还伞", location=None)
    assert result.requested_field == "location"
    assert result.executed_tools == []

async def test_return_search_excludes_full_stations_and_marks_update_time(station_runner):
    result = await station_runner.run("附近哪里可以还伞", location=hangzhou_location())
    assert all(card.available_docks > 0 for card in result.cards)
    assert all(card.inventory_updated_at for card in result.cards)
```

- [ ] **Step 2: Run the station tests and verify the scenario is missing**

- [ ] **Step 3: Implement location collection, purpose detection, query execution, filtering, and distance sorting**

- [ ] **Step 4: Register the subgraph and run the station plus complete agent suites**

- [ ] **Step 5: Commit**

```bash
git add services/api/app/agent services/api/tests/agent/test_nearby_station.py
git commit -m "feat: add nearby umbrella station guidance"
```

### Task 13: Persistent Idempotent SSE Chat API

**Files:**
- Create: `services/api/app/streaming/events.py`
- Create: `services/api/app/streaming/encoder.py`
- Create: `services/api/app/streaming/service.py`
- Create: `services/api/app/streaming/routes.py`
- Create: `services/api/tests/streaming/test_chat_stream.py`
- Modify: `services/api/app/main.py`

**Interfaces:**
- Consumes: identity, conversation persistence, and `AgentRunner`.
- Produces: `POST /api/v1/conversations/{id}/messages:stream` with `text/event-stream`.
- Produces ordered events `message.started`, `assistant.delta`, `tool.started`, `tool.completed`, `business_card`, `assistant.completed`, and `error`, each with `request_id`, `conversation_id`, and `sequence`.

- [ ] **Step 1: Write failing API tests for event order, persistence, duplicate retries, reconnect replay, and ownership**

```python
async def test_duplicate_idempotency_key_replays_without_duplicate_side_effects(client, auth):
    first = await stream(client, auth, key="turn-1", text="还是还不了")
    second = await stream(client, auth, key="turn-1", text="还是还不了")
    assert completed_message_id(first) == completed_message_id(second)
    assert await count_user_messages("turn-1") == 1
    assert await count_support_tickets("turn-1") <= 1

async def test_other_user_cannot_stream_to_conversation(client, foreign_auth, conversation):
    response = await client.post(f"/api/v1/conversations/{conversation.id}/messages:stream", headers=foreign_auth)
    assert response.status_code == 404
```

- [ ] **Step 2: Run the streaming tests and verify the route is missing**

- [ ] **Step 3: Define the SSE envelope and encoder, including monotonically increasing sequence values**

- [ ] **Step 4: Implement the transactional send workflow and message-length validation**

Reject empty or over-limit text before model execution. Persist the user message before Agent execution, record tool/model events, persist one assistant message on completion, and save an error system event on failure.

- [ ] **Step 5: Implement Redis-backed idempotency and bounded event replay**

PostgreSQL uniqueness remains the final duplicate guard; Redis accelerates active-turn lookup and short replay.

- [ ] **Step 6: Trigger rolling summary and controlled long-term-memory updates after a successfully persisted turn**

- [ ] **Step 7: Register the route and run all streaming, conversation, context, and agent tests**

- [ ] **Step 8: Commit**

```bash
git add services/api/app/streaming services/api/app/main.py services/api/tests/streaming
git commit -m "feat: stream persistent idempotent agent turns"
```

### Task 14: Complete H5 History, Streaming, and Business Cards

**Files:**
- Create: `apps/web/src/api/contracts.ts`
- Create: `apps/web/src/api/client.ts`
- Create: `apps/web/src/api/sse.ts`
- Create: `apps/web/src/features/session/session-store.ts`
- Create: `apps/web/src/features/chat/chat-store.ts`
- Create: `apps/web/src/features/chat/queries.ts`
- Create: `apps/web/src/components/chat/MessageList.tsx`
- Create: `apps/web/src/components/chat/MessageBubble.tsx`
- Create: `apps/web/src/components/chat/StreamingMessage.tsx`
- Create: `apps/web/src/components/chat/BusinessCard.tsx`
- Create: `apps/web/src/components/chat/IssueTicketCard.tsx`
- Create: `apps/web/src/components/chat/LocationPicker.tsx`
- Create: `apps/web/src/components/chat/ConversationDrawer.tsx`
- Create: `apps/web/src/features/chat/ChatPage.tsx`
- Create: `apps/web/src/features/chat/ChatPage.test.tsx`
- Modify: `apps/web/src/app/App.tsx`

**Interfaces:**
- Consumes: bootstrap, conversation, message-history, and SSE APIs.
- Produces: full cursor-paginated history, incremental assistant text, tool status, billing/station/ticket cards, safe reconnect, and retry UI.

- [ ] **Step 1: Write failing UI tests for bootstrap, history pagination, streaming updates, cards, and retry state**

```tsx
it("keeps persisted history while rendering a streamed business card", async () => {
  server.use(historyPage(oldMessages), streamTurn([delta("正在查询"), stationCard(stations), completed()]))
  render(<ChatPage />)
  expect(await screen.findByText(oldMessages[0].text)).toBeVisible()
  await send("附近哪里可以还伞")
  expect(await screen.findByText("正在查询")).toBeVisible()
  expect(await screen.findByRole("article", { name: stations[0].name })).toBeVisible()
})

it("reuses the same idempotency key after a dropped stream", async () => {
  render(<ChatPage />)
  await send("还不了伞")
  await retryDroppedTurn()
  expect(capturedRequestKeys()).toEqual(["turn-fixed", "turn-fixed"])
})
```

- [ ] **Step 2: Run the ChatPage test and verify missing client/store/component failures**

- [ ] **Step 3: Implement typed HTTP contracts, demo-session bootstrap, and token handling in memory/session storage**

Do not put API keys or long-lived credentials in the browser.

- [ ] **Step 4: Implement the POST streaming parser and Zustand turn state machine**

- [ ] **Step 5: Implement cursor-paginated history, message virtualization, and scroll anchoring**

- [ ] **Step 6: Implement message, tool status, station, billing, ticket, and explicit location-picker UI with loading/error/retry states**

- [ ] **Step 7: Add safe-area, virtual-keyboard, weak-network, and touch-target styles**

- [ ] **Step 8: Run the full Vitest suite, TypeScript check, and production build**

Run: `npm --prefix apps/web test -- --run && npm --prefix apps/web run typecheck && npm --prefix apps/web run build`

- [ ] **Step 9: Commit**

```bash
git add apps/web
git commit -m "feat: connect H5 to streaming AI customer service"
```

### Task 15: Gateway, Docker Compose, Observability, and End-to-End Acceptance

**Files:**
- Create: `services/api/Dockerfile`
- Create: `services/mock-business/Dockerfile`
- Create: `apps/web/Dockerfile`
- Create: `infra/nginx/nginx.conf`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `services/api/app/core/logging.py`
- Create: `services/api/app/core/middleware.py`
- Create: `services/api/tests/core/test_middleware.py`
- Create: `tests/e2e/package.json`
- Create: `tests/e2e/playwright.config.ts`
- Create: `tests/e2e/customer-service.spec.ts`
- Create: `README.md`
- Modify: `services/api/app/main.py`

**Interfaces:**
- Consumes: all prior services and UI.
- Produces: `gateway`, `api`, `mock-business`, `postgres`, and `redis` Compose services.
- Produces correlated JSON logs carrying `request_id`, `conversation_id`, `user_id`, `model_call_id`, and `tool_call_id` where applicable.
- Produces one-command local startup and three browser-level acceptance flows.

- [ ] **Step 1: Write failing Playwright tests for the three required user journeys**

```typescript
test("return failure diagnoses station capacity and creates a ticket", async ({ page }) => {
  await openAs(page, "demo-return-user")
  await send(page, "伞插不进去")
  await expect(page.getByText("附近可还网点")).toBeVisible()
  await send(page, "还是解决不了")
  await expect(page.getByText(/工单/)).toBeVisible()
})

test("billing dispute shows verified line items without refund action", async ({ page }) => {
  await openAs(page, "demo-billing-user")
  await send(page, "费用不对")
  await expect(page.getByText("计费明细")).toBeVisible()
  await expect(page.getByRole("button", { name: /退款/ })).toHaveCount(0)
})

test("nearby search returns stations with return capacity", async ({ page }) => {
  await openAs(page, "demo-nearby-user")
  await chooseQuickAction(page, "附近网点")
  await provideMockLocation(page)
  await expect(page.getByText(/可还空位/).first()).toBeVisible()
})
```

- [ ] **Step 2: Run the Playwright suite and verify it fails because the composed environment is absent**

- [ ] **Step 3: Write and run failing middleware tests for request-ID propagation, oversized input rejection, and per-user/IP chat rate limiting**

- [ ] **Step 4: Add request-ID, structured-logging, error-mapping, input-limit, and rate-limit middleware**

- [ ] **Step 5: Add production Dockerfiles and Nginx configuration**

Nginx serves the H5, proxies `/api`, forwards/generates request IDs, disables buffering for SSE, and applies basic per-IP chat limits.

- [ ] **Step 6: Add Compose health checks, migrations, seed startup, persistent volumes, and service dependency conditions**

- [ ] **Step 7: Add `.env.example` without secrets**

Document `MODEL_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL`, database/Redis URLs, internal mock token, and signed demo-token secret. Provide `MODEL_PROVIDER=fake` for offline test runs.

- [ ] **Step 8: Write the README setup, architecture, demo accounts, scenario script, privacy rules, and test commands**

- [ ] **Step 9: Start the clean composed environment and verify health**

Run: `docker compose down -v && docker compose up --build -d`

Expected: all five services become healthy and `http://localhost/health` plus the H5 are reachable.

- [ ] **Step 10: Run backend, frontend, and end-to-end verification**

```bash
uv run --project services/api pytest services/api/tests -v
uv run --project services/mock-business pytest services/mock-business/tests -v
npm --prefix apps/web test -- --run
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
npm --prefix tests/e2e test
```

Expected: every command exits 0; the three Playwright journeys pass.

- [ ] **Step 11: Verify no private or secret files are tracked**

Run: `git ls-files | rg '(\.env$|\.pdf$|\.docx?$|private/|personal/)'`

Expected: no output. Then run a secret scan if available and inspect `git status --short`.

- [ ] **Step 12: Commit**

```bash
git add services/api apps/web services/mock-business infra tests docker-compose.yml .env.example README.md
git commit -m "feat: deliver local umbrella AI customer service demo"
```

## Final Verification Gate

- [ ] Run the complete command set from Task 15 Step 9 from a clean checkout.
- [ ] Re-run all three Playwright journeys with `MODEL_PROVIDER=fake` for determinism.
- [ ] Run one manual smoke conversation with `MODEL_PROVIDER=openai` and verify streaming, tool calls, usage logging, and fallback behavior without committing the key.
- [ ] Refresh the browser mid-conversation and verify full history returns from PostgreSQL.
- [ ] Trigger the context threshold and verify a summary is created while original messages remain visible.
- [ ] Retry one dropped stream and verify one user message and at most one support ticket exist.
- [ ] Inspect structured logs and trace one turn through request, model, tool, and completion IDs.
- [ ] Confirm `git ls-files` contains no resume, personal document, `.env`, API key, or runtime database/log file.

