# Agent Support

公共雨伞智能客服演示项目。当前包含 React H5、FastAPI SSE、SQLite 会话持久化、历史会话切换，以及还伞失败、计费问题、附近网点三种模拟业务流程。

## 本地启动

### 1. FastAPI 后端

```bash
cd services/api
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

后端地址：`http://127.0.0.1:8000`

健康检查：`http://127.0.0.1:8000/health`

### 2. React H5

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

cd ../../apps/web
npm run typecheck
npm run build
```

## 当前边界

- FastAPI 返回确定性的模拟 Agent 流，尚未接入真实 OpenAI 模型。
- SQLite 用于本地演示；Repository 边界可在后续替换为 PostgreSQL。
- 首期未实现 RAG 和人工客服接管。
- `.env`、简历、PDF、运行时数据库和日志不会提交到仓库。
