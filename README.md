# Agent Support

公共雨伞智能客服演示项目。当前包含 React H5、FastAPI SSE、SQLite 会话持久化、历史会话切换、独立的模拟公共雨伞业务服务、可切换的 OpenAI-Compatible Model Gateway、LangGraph Agent、安全 Tool Executor、长短期记忆、上下文压缩、轮次 Trace 与自动评测。还伞失败、计费问题和附近网点三种流程的数据都通过白名单工具查询，不在前端或模型中编造订单事实。

## 本地启动

### 1. 模拟公共雨伞业务服务

```bash
cd services/mock-business
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

业务服务地址：`http://127.0.0.1:8010`

接口文档：`http://127.0.0.1:8010/docs`

固定演示用户：

- `demo-user`：H5 默认用户，具有进行中的租借和计费记录。
- `demo-return-user`：还伞失败场景，目标网点在线但空位为 0。
- `demo-billing-user`：计费争议场景，具有可解释的基础费用和超时费用。
- `demo-nearby-user`：附近网点查询场景。

### 2. FastAPI 客服后端

打开另一个终端：

```bash
cd services/api
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

后端地址：`http://127.0.0.1:8000`

健康检查：`http://127.0.0.1:8000/health`

客服后端通过 `APP_BUSINESS_BASE_URL` 和 `APP_BUSINESS_INTERNAL_TOKEN` 调用业务服务，默认值可直接用于本地开发。

Model Gateway 默认使用 `MODEL_PROVIDER=fake`，不需要外部 API Key。Fake Provider 仍会经过统一的模型流式接口，并记录模型调用、Token 估算、耗时和状态。

Agent 使用 LangGraph 显式编排场景识别、工具规划、工具执行、结果组装和安全降级。业务工具只允许：查询活跃租借、最近订单、计费、网点、附近网点，以及幂等创建客服工单。模型不能提供或覆盖当前用户 ID，也没有结束订单、修改账单或退款工具。每轮最多调用 `AGENT_MAX_TOOL_CALLS` 次工具，默认值为 6。

记忆层将数据分成两部分：

- 会话短期记忆：前端和历史接口始终展示完整消息，模型只接收最近 `MEMORY_RECENT_MESSAGE_LIMIT` 条消息和最多 `MEMORY_SUMMARY_MAX_CHARS` 字的滚动摘要。
- 用户长期记忆：只保存用户明确提供的称呼、常用网点、回复风格和回复语言，并按当前用户跨会话读取。订单、金额、租借状态和网点库存不会写入长期记忆；手机号、银行卡等敏感信息不会被提取。

查看或清除当前演示用户的长期记忆：

```bash
curl -H 'X-Demo-User: demo-user' http://127.0.0.1:8000/api/v1/memories
curl -X DELETE -H 'X-Demo-User: demo-user' http://127.0.0.1:8000/api/v1/memories
```

### 可观测性

每轮 SSE 对话都会生成 `traceId`，并通过同一个 `request_id` 关联 Agent 场景、上下文使用情况、Tool Span、Model Span、Token、耗时和安全降级状态。接口只返回当前用户的 Trace：

```bash
curl http://127.0.0.1:8000/api/v1/observability/summary
curl http://127.0.0.1:8000/api/v1/observability/traces
curl http://127.0.0.1:8000/api/v1/observability/traces/{trace_id}
```

汇总指标包括对话轮数、平均耗时、工具成功率、模型失败率、安全降级次数和累计 Token。详细 Trace 会列出每个工具与模型调用的状态、错误码和耗时。

### Agent 自动评测

先启动模拟业务服务，然后在 `services/api` 执行：

```bash
uv run python -m app.evals
```

评测集位于 `services/api/evals/support_cases.json`，当前覆盖还伞失败、退款诉求、附近网点、未知意图、提示注入和用户偏好更新。任一场景、必需工具、禁用工具或关键安全文案不符合预期时，命令会以非零状态退出。

如需接入 OpenAI 或支持 Chat Completions 协议的兼容服务，在仓库根目录复制配置：

```bash
cp .env.example .env
```

然后设置：

```text
MODEL_PROVIDER=openai
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=your-model-name
```

从 `services/api` 启动时加载根目录配置：

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --env-file ../../.env
```

`OPENAI_BASE_URL` 可以替换成其他兼容服务地址；API Key 只保存在被 Git 忽略的 `.env` 中。

### 3. React H5

打开另一个终端：

```bash
cd apps/web
npm install
npm run dev -- --host 127.0.0.1
```

前端地址：`http://127.0.0.1:5173`

Vite 会把 `/api` 请求代理到本机 `8000` 端口。

## 验证

```bash
cd services/api
uv run pytest

cd ../mock-business
uv run pytest

cd ../../apps/web
npm run typecheck
npm run build
```

## 当前边界

- 默认使用 Fake Model，配置 `MODEL_PROVIDER=openai` 后才会调用真实的 OpenAI-compatible 模型。
- Model Gateway 已统一文本增量、Tool Call 增量、Usage、完成事件、结构化输出、超时重试和失败记录。
- LangGraph Agent 已覆盖还伞失败、计费争议、附近网点和未知意图安全降级。
- Tool Executor 使用严格参数 Schema、用户身份注入、白名单、调用上限和 `tool_calls` 审计记录。
- 完整聊天记录保存在 `messages` 表；会话摘要保存在 `conversation_memories`，跨会话偏好保存在 `user_memories`。
- 模型上下文由安全规则、滚动摘要、白名单长期偏好、近期消息和本轮已核验业务结果组成。
- “还是不行”“那怎么办”等省略主语的追问会参考近期用户消息继承场景；无关新问题不会被旧场景带偏。
- 当前场景预路由和记忆提取采用确定性规则，便于本地演示、审计和自动化测试。
- `turn_traces` 记录每轮汇总，详情通过 `request_id` 关联 `tool_calls` 和 `model_calls`，不重复保存业务结果正文。
- 固定评测集可直接调用真实 Agent Graph 与模拟业务 API，默认不依赖外部模型和 API Key。
- 业务订单、计费、租借、网点和工单由独立 `mock-business` API 提供。
- SQLite 用于本地演示；Repository 边界可在后续替换为 PostgreSQL。
- 首期未实现 RAG 和人工客服接管。
- `.env`、简历、PDF、运行时数据库和日志不会提交到仓库。
