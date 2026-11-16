# Agent Support

公共雨伞智能客服演示项目。当前包含 React H5、FastAPI SSE、SQLite 会话持久化、历史会话切换、独立的模拟公共雨伞业务服务，以及可切换的 OpenAI-Compatible Model Gateway。还伞失败、计费问题和附近网点三种流程的数据都通过业务适配器查询，不在前端或模型中编造订单事实。

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
- 场景识别暂时仍是确定性规则；LangGraph Agent 和安全 Tool Executor 将在后续阶段接入。
- 业务订单、计费、租借、网点和工单由独立 `mock-business` API 提供。
- SQLite 用于本地演示；Repository 边界可在后续替换为 PostgreSQL。
- 首期未实现 RAG 和人工客服接管。
- `.env`、简历、PDF、运行时数据库和日志不会提交到仓库。
