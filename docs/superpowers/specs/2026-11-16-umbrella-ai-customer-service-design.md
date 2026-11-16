# 公共雨伞智能客服系统设计

## 1. 项目意图

本项目是一套可放入个人简历并能在本地完整演示的公共雨伞 AI 客服系统。客户从微信小程序的统一“客服”入口跳转到移动端 H5，H5 只携带当前用户身份，不绑定某个订单。AI 客服通过对话理解用户问题，按需查询该用户的当前租借、最近订单、计费、设备和网点数据，并完成问题解释、操作指引或异常工单创建。

第一期只实现 AI 对客服务，不实现人工客服实时接管。所有业务数据由独立的模拟公共雨伞服务提供，整个项目通过 Docker Compose 在本地一键启动。项目重点展示移动端客服 UI、API 网关与适配、Agent 编排、Tool Calling、业务接口适配、长短期记忆、上下文压缩、流式响应、风险控制和可观测性。

## 2. 目标

- 提供适合微信内置浏览器的移动端 H5 客服对话体验。
- 完整演示三个核心场景：还伞失败、计费争议、附近网点查询。
- 让 Agent 根据当前用户身份自行查询相关业务数据，而不是要求入口绑定订单。
- 完整保存所有聊天记录，同时只向模型发送压缩后的有效上下文。
- 保存受控的用户长期记忆，使跨会话服务具有连续性。
- 通过统一 Model Gateway 接入 OpenAI，并保留切换其他 OpenAI-compatible 模型的能力。
- 通过业务适配器隔离 Agent 与模拟公共雨伞 API，未来接入真实系统时不改 Agent 主流程。
- 通过 Docker Compose 提供可复现、可演示、可测试的本地环境。

## 3. 非目标

第一期明确不包含：

- RAG、向量数据库、知识库切片与召回。
- 人工客服工作台、排队、分配、人工接管和 WebSocket 坐席通信。
- 微信小程序本身；只实现可被小程序链接打开的 H5。
- 真实订单、支付、退款、设备控制或生产用户数据。
- 自动退款、自动结束订单等不可逆高风险操作。
- 为展示复杂度而拆分大量微服务。

第二期可在现有边界上增加人工客服工作台、接待队列、AI 转人工摘要、会话接管/归还和实时通信。

## 4. 反目标

即使功能可运行，出现以下情况也视为设计失败：

- 聊天记录只存在前端或进程内，刷新或重启后丢失。
- 每次调用模型都发送全部历史消息，导致成本和上下文无限增长。
- 长期记忆未经筛选就保存模型猜测、敏感信息或全部聊天文本。
- Agent 直接依赖模拟服务的接口结构，替换真实业务 API 时必须重写流程。
- 模型可以绕过风险策略直接修改订单、计费或退款状态。
- 为了“微服务感”引入无法解释其价值的服务拆分和运维复杂度。
- UI 直接套用桌面组件，忽视微信 H5 的软键盘、安全区、触控和弱网场景。

## 5. 已考虑的实现路线

### 5.1 方案 A：模块化单体客服后端 + 独立模拟业务服务（已选择）

React H5、FastAPI 客服后端和独立的 Mock 公共雨伞服务通过明确 API 交互。客服后端内部按领域模块划分，但部署为单个服务。它保留真实的网关、模型适配、业务适配和持久化边界，开发量仍然可控。

选择原因：能完整展示工程设计与 Agent 能力，同时避免把时间消耗在服务治理上；未来可以按现有模块边界拆分服务。

### 5.2 方案 B：完整微服务

将网关、会话、Agent、记忆、订单、设备、网点和工单拆成独立服务。边界清晰，但第一期数据规模和团队规模不足以支持这种复杂度，大量工作会落在服务发现、配置、链路和部署，而不是用户问题解决。

### 5.3 方案 C：轻量聊天应用

React 与 FastAPI 单服务直接完成对话、规则和模拟数据，不使用 LangGraph、Redis或独立业务适配。交付最快，但无法充分展示 Agent 状态编排、业务解耦、记忆和风险控制，不适合作为核心简历项目。

## 6. 总体架构

```text
微信小程序客服入口（未来）
          |
          | H5 URL + 短期签名用户令牌
          v
React H5（shadcn/ui）
          |
          v
Nginx API Gateway
  - 静态资源、路由、Request ID、限流、超时
          |
          v
FastAPI Customer Service API
  - 身份/API适配
  - 会话与消息服务
  - LangGraph Agent Runtime
  - 上下文与记忆管理
  - Tool Registry / Risk Policy
  - Model Gateway -> OpenAI Adapter -> OpenAI API
  - Umbrella Business Adapter
          |                          |
          |                          +--> PostgreSQL
          |                          +--> Redis
          v
Mock Umbrella Business API
  - 用户、租借、订单、计费、网点、设备、工单
```

请求处理主链路：

```text
用户消息
-> 网关
-> 身份与请求适配
-> 保存原始消息
-> 加载会话状态和记忆
-> 组装压缩上下文
-> Agent 场景识别与路由
-> Tool 调用及业务 API 适配
-> 结果校验与风险判断
-> 流式生成回复
-> 保存回复、工具记录和新状态
-> 必要时更新摘要或长期记忆
```

## 7. 前端设计

### 7.1 技术栈

- React + TypeScript + Vite
- shadcn/ui + Tailwind CSS
- Zustand：当前用户、活跃会话、流式消息和连接状态
- TanStack Query：历史会话、分页消息、网点等服务端状态
- React Router：H5 路由
- Fetch streaming：使用 `text/event-stream` 读取 POST 消息接口的 SSE 数据

不引入完整聊天 UI 框架。shadcn/ui 用于 Button、Sheet、Dialog、Drawer、Toast、Skeleton 等基础交互，聊天和业务卡片由项目自行设计。

### 7.2 页面与组件

第一期只有一个主要 H5 客服页面，但按组件拆分：

- `ChatPage`：页面容器和会话初始化。
- `ChatHeader`：品牌、在线状态、会话入口。
- `MessageList`：按游标向上分页加载全部历史消息。
- `MessageBubble`：用户、AI、系统和错误消息。
- `StreamingMessage`：增量文本、工具执行状态和停止生成。
- `QuickActions`：还伞失败、计费问题、附近网点三个快捷入口。
- `BusinessCard`：订单、计费明细、设备状态和网点列表卡片。
- `ChatComposer`：输入、发送、重试和软键盘适配。
- `IssueTicketCard`：AI 无法闭环时展示已创建的待处理工单。
- `ConversationDrawer`：历史会话列表；每个会话仍能看到完整消息。

### 7.3 移动端约束

- 以 375–430px 宽度为主要设计基准，同时支持普通移动浏览器。
- 处理 `safe-area-inset-top/bottom`、微信内置浏览器和虚拟键盘顶起。
- 可点击区域不小于适合触控的尺寸，输入框始终可达。
- SSE 断开时展示连接状态，并允许安全重连；不能重复提交同一用户消息。
- 长历史记录采用游标分页和列表窗口化，不能一次加载全部 DOM。
- 业务卡片优先展示用户可采取的下一步，而不是后端原始字段。

## 8. 网关与 API 适配层

### 8.1 Nginx Gateway

Nginx 负责：

- 提供 React 构建后的静态资源。
- 将 `/api/*` 路由到 FastAPI。
- 生成或透传 `X-Request-ID`。
- 对聊天接口按用户和 IP 限流。
- 为流式接口关闭不恰当的响应缓冲并设置合理超时。
- 统一基础安全头、压缩和 API 错误页。

本地环境不模拟复杂 OAuth。H5 使用短期签名 Demo Token 表示当前用户，FastAPI 的身份适配器完成验证并生成 `RequestContext`。未来小程序只需换成真实的登录换票接口，后续会话服务不依赖微信字段。

### 8.2 API 适配职责

适配层将外部请求转换为稳定的内部命令：

- 用户令牌 -> `CurrentUser`
- HTTP 消息请求 -> `SendMessageCommand`
- 内部领域错误 -> 稳定错误码和用户可理解信息
- SSE 内部事件 -> 统一前端事件协议

不得在控制器中直接调用模型或模拟业务 API。

## 9. 后端模块

FastAPI 后端采用模块化单体，主要模块如下：

1. `identity`：Demo Token 验证和当前用户上下文。
2. `conversation`：会话生命周期、消息保存和分页读取。
3. `agent`：LangGraph 状态、节点和场景路由。
4. `context`：模型上下文组装、Token 预算和滚动摘要。
5. `memory`：用户长期记忆的候选提取、校验、保存、过期和读取。
6. `tools`：Tool Schema、注册、参数校验、权限和执行记录。
7. `business_adapter`：将稳定领域调用转换为 Mock Umbrella API。
8. `model_gateway`：模型调用、流式事件、Tool Calling 和错误统一。
9. `risk`：高风险动作拦截、输出校验和降级策略。
10. `ticket`：创建第一期待处理异常工单。
11. `observability`：结构化日志、指标和请求/会话/模型调用关联。

控制器依赖应用服务；应用服务依赖领域接口；模型和业务 API 都通过 Adapter 实现，避免基础设施进入 Agent 节点。

## 10. Model Gateway

Agent 只依赖统一的 `ModelGateway` 接口，不感知 OpenAI SDK：

```text
stream_chat(request) -> AsyncIterator[ModelEvent]
complete_structured(request, schema) -> StructuredResult
```

统一处理：

- 系统提示、消息和 Tool Schema 转换。
- 文本增量、Tool Call 增量、完成、用量和错误事件。
- 结构化输出校验。
- 超时、有限重试、指数退避和取消。
- 模型名称、温度、Token 上限等配置。
- Token 用量、延迟和失败原因日志。

第一期提供 `OpenAIAdapter`。通过 `MODEL_PROVIDER`、`OPENAI_API_KEY`、`OPENAI_MODEL` 等环境变量配置；后续新增其他 OpenAI-compatible Adapter 时，不修改 Agent 和业务层。测试环境提供确定性的 Fake Adapter，不依赖外部网络。

## 11. Agent 编排

### 11.1 LangGraph 状态

核心 `AgentState` 包含：

- `conversation_id`、`user_id`
- 当前用户消息
- 场景：`return_failure`、`billing_dispute`、`nearby_station`、`unknown`
- 当前阶段和已收集参数
- 活跃租借与候选订单引用
- 最近工具结果的精简表示
- 风险等级和允许动作
- 会话摘要和有效长期记忆
- 待发送回复和下一步建议

状态中的业务引用使用内部领域 ID，不直接保存第三方原始响应。

### 11.2 图节点

```text
load_context
-> classify_scenario
-> route_scenario
-> collect_missing_information（必要时）
-> select_tool
-> validate_tool_request
-> execute_tool
-> validate_tool_result
-> decide_next_step
-> generate_response
-> persist_turn
-> maybe_summarize
-> maybe_update_memory
```

无法识别、业务 API 故障或模型错误时进入 `safe_fallback`，提供明确说明和可重试动作；如果问题仍不能解决，创建待处理工单。图应设置最大工具调用次数和最大循环次数，防止 Agent Loop 失控。

## 12. 三个核心业务流程

### 12.1 还伞失败

1. 用户描述无法还伞或还伞后仍计费。
2. Agent 根据当前用户查询活跃租借，无需入口携带订单。
3. 如果没有活跃租借，查询最近订单并向用户确认具体问题。
4. 查询目标网点、设备在线状态和空闲伞位；缺少位置时通过对话收集。
5. 根据结果给出重新插伞、换可用网点或检查订单状态等安全指引。
6. 仍无法解决时创建 `return_failure` 工单，保存租借、设备、网点和排查摘要。
7. 第一阶段不自动结束订单、不改计费记录。

### 12.2 计费争议

1. 用户描述持续计费、费用异常或退款问题。
2. 查询活跃租借和最近订单，必要时让用户从候选记录中确认。
3. 获取计费明细和规则化的费用计算结果。
4. Agent 只解释可验证事实，不自行承诺退款。
5. 如果规则无法解释差异，创建 `billing_dispute` 工单并展示工单状态。
6. 所有金额和时间必须来自业务工具结果，不允许模型自行计算关键金额。

### 12.3 附近网点查询

1. 用户提出找伞或找还伞点。
2. 优先使用前端明确授权的位置；没有位置时允许输入地点或选择模拟位置。
3. 查询附近网点、可借雨伞、可还空位、距离和在线状态。
4. 返回结构化网点卡片，按用户目的过滤并排序。
5. 数据不足时说明更新时间，不把过期库存描述为实时保证。

## 13. Tool 与业务适配

Agent 可见的稳定工具：

- `get_active_rental(user_id)`
- `list_recent_orders(user_id, limit)`
- `get_order_billing(order_id)`
- `get_station_status(station_id)`
- `find_nearby_stations(location, purpose, radius)`
- `create_support_ticket(user_id, category, references, summary)`

Tool Executor 负责参数 Schema 校验、超时、幂等、权限、调用次数限制和审计。Agent 不能访问任意 URL，也不能自行拼接业务请求。

`UmbrellaBusinessAdapter` 把上述工具转换为模拟业务 API。未来真实 API 字段、鉴权或错误码发生变化时，仅修改 Adapter。

模拟服务至少提供：

- 用户与活跃租借查询。
- 最近订单和计费明细查询。
- 网点、设备、库存和空位查询。
- 支持工单创建和查询。
- 固定种子场景，确保三条演示流程可重复运行。

## 14. 聊天记录、上下文与记忆

### 14.1 完整记录

所有用户消息、AI 回复、系统事件、Tool Call 和工单事件都持久化。前端始终从这些记录分页展示完整历史，摘要不能覆盖或删除原始消息。

### 14.2 当前会话记忆

模型上下文采用滚动压缩：

- 达到约 20 轮或配置的 Token 阈值时，对较早内容生成结构化摘要。
- 最近 10–15 条原始消息继续保留。
- 摘要保存当前问题、已确认事实、已尝试动作、工具关键结果、未决事项和下一步。
- 每个摘要记录覆盖的消息范围和版本，便于追溯。

每次调用模型的上下文顺序固定为：

```text
系统规则
-> 当前用户基本信息
-> 有效长期记忆
-> 当前会话摘要
-> 最近原始消息
-> 当前用户消息
```

### 14.3 用户长期记忆

长期记忆只保存对后续客服有明确价值的结构化事实，例如近期反复还伞失败、未解决计费工单或用户确认的常用网点。每条记忆包含类型、结构化内容、来源会话、置信度、创建时间、有效期和状态。

写入规则：

- 模型只能提出候选记忆，由确定性规则校验后写入。
- 不保存模型推测、支付凭证、完整对话复制或无关个人信息。
- 未解决问题到期或工单解决后可失效。
- 用户基本资料与 Agent 记忆分表保存。

这套数据库检索不属于 RAG；第一期不使用向量召回。

## 15. 数据模型

第一期主要表：

- `users`：模拟用户基础信息。
- `conversations`：会话标题、状态、`service_mode`、`handoff_status`、预留的 `assigned_agent_id`。
- `messages`：完整消息、角色、类型、内容、状态和顺序。
- `conversation_states`：LangGraph 当前状态快照和版本。
- `conversation_summaries`：滚动摘要及覆盖消息范围。
- `user_memories`：受控长期记忆、来源、置信度、有效期和状态。
- `tool_calls`：工具参数摘要、结果摘要、耗时、状态和错误。
- `support_tickets`：异常类别、业务引用、排查摘要和状态。
- `model_calls`：模型、Token、延迟、状态和关联请求。

使用 PostgreSQL 作为事实数据源；Redis 只用于短期缓存、限流、流式连接状态和幂等键，不能作为聊天记录的唯一存储。

## 16. HTTP 与流式接口

建议的外部 API：

- `POST /api/v1/demo/session`：用演示用户换取短期签名 Token。
- `GET /api/v1/bootstrap`：返回当前用户、最近会话和快捷问题。
- `POST /api/v1/conversations`：创建会话。
- `GET /api/v1/conversations`：分页读取会话列表。
- `GET /api/v1/conversations/{id}/messages`：按游标读取完整消息。
- `POST /api/v1/conversations/{id}/messages:stream`：发送消息并以 SSE 返回事件。
- `POST /api/v1/messages/{id}/feedback`：记录回复反馈。
- `GET /api/v1/tickets/{id}`：查询第一期待处理工单。

SSE 事件至少包含：

- `message.started`
- `assistant.delta`
- `tool.started`
- `tool.completed`
- `business_card`
- `assistant.completed`
- `error`

事件包含 `request_id`、`conversation_id` 和可重放的事件序号。消息发送接口使用幂等键，前端重连不能重复创建用户消息或工单。

## 17. 风险控制与安全

- Tool 白名单和严格参数 Schema；模型不能执行任意函数。
- 金额、订单状态、设备状态必须由工具结果提供。
- 第一阶段所有写操作仅限创建模拟工单，不允许修改订单、退款或设备。
- 对模型输入输出做长度限制、内容类型校验和敏感字段脱敏。
- API Key 只在后端环境变量中，不能进入前端构建产物或日志。
- 日志记录用户和订单的内部引用，不记录完整敏感数据。
- 模型或业务服务不可用时，返回可解释的降级结果，不伪造处理成功。

## 18. 可观测性

每次请求贯穿以下关联标识：`request_id`、`conversation_id`、`user_id`、`model_call_id`、`tool_call_id`。

至少记录：

- HTTP 状态和接口延迟。
- 首 Token 延迟、完整响应延迟和 Token 用量。
- Tool 调用成功率、耗时和错误类别。
- 每轮 Agent 节点、循环次数和终止原因。
- 摘要触发、长期记忆候选与写入结果。
- SSE 断连与重连次数。

本地第一期使用结构化 JSON 日志和健康检查即可；指标接口预留给后续 Prometheus。

## 19. Docker Compose

Compose 包含：

- `gateway`：Nginx，提供 H5 静态资源并反向代理 API。
- `api`：FastAPI 客服后端。
- `mock-business`：独立 FastAPI 模拟公共雨伞业务服务。
- `postgres`：业务持久化。
- `redis`：缓存、限流和流式辅助状态。

启动流程负责数据库迁移和固定演示数据初始化。用户复制 `.env.example`、配置 OpenAI Key 和模型名后执行一次 `docker compose up --build` 即可访问。测试环境可选择 Fake Model Adapter，使自动化测试无需外网或真实 Key。

## 20. 测试与验收

### 20.1 测试层级

- 单元测试：上下文预算、摘要选择、记忆写入规则、风险策略和 Adapter 映射。
- Agent 图测试：使用 Fake Model 和 Fake Tools 验证节点路由、循环上限和降级。
- API 集成测试：PostgreSQL/Redis/模拟业务服务下的消息、SSE、幂等和分页。
- 前端组件测试：消息状态、业务卡片、错误、重连和历史分页。
- 端到端测试：三条固定种子场景从 H5 输入到最终结果。

### 20.2 第一阶段验收标准

- Docker Compose 能从干净环境启动全部本地服务。
- 演示用户可以创建会话、刷新页面并看到完整聊天记录。
- 长对话触发摘要后，完整消息仍可查看，模型上下文不随历史无限增长。
- 还伞失败流程能查询活跃租借与设备/网点状态，并在无法闭环时创建工单。
- 计费争议流程展示真实模拟计费明细，模型不能自行编造金额或执行退款。
- 附近网点流程返回结构化网点卡片和可借/可还信息。
- 模型、业务服务或 SSE 失败时，前端展示明确可恢复状态。
- 工具、模型和请求日志可以通过关联 ID 串起一次完整对话。

## 21. 为第二阶段预留的边界

- `conversations.service_mode` 支持 `ai`、`human`、`hybrid`。
- `handoff_status` 和 `assigned_agent_id` 作为预留字段，但第一期不实现人工接管逻辑。
- 消息模型支持未来的人工客服角色。
- `support_tickets` 可成为转人工队列的来源。
- Agent 可在第二阶段增加生成转人工摘要的节点。
- 前端保留系统消息和接管状态组件边界，但第一期不展示虚假的“人工在线”。

## 22. 留给实现者的非关键决策

实现者可以在不改变产品边界的前提下决定：

- 具体目录命名、代码格式化和 lint 工具配置。
- UI 的品牌色、插画和微动效，只需保持移动端清晰和专业。
- 摘要 Token 阈值的精确默认值，但必须可配置并有测试。
- Redis 客户端、HTTP 客户端和数据库迁移工具的具体库。
- OpenAI 的具体模型名；必须通过环境变量配置，不能硬编码业务逻辑。

