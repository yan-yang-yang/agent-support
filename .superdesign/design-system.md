# Agent Support H5 Design System

## Product context

Agent Support is a mobile H5 AI customer-service experience for a public-umbrella business. Customers enter from a WeChat mini-program with only their current user identity. The first release demonstrates three flows: return failure, billing dispute, and nearby-station search. This draft is frontend-only and simulates streaming AI replies locally.

The experience must feel like a reliable service desk, not a marketing page or a generic chatbot. The primary job is to calm an urgent user, show what the AI is checking, and present the next safe action in a glance.

## Target screen

- One mobile conversation page, designed first for 390 x 844 px and usable from 375–430 px.
- Header with service identity, online state, and a subtle history action.
- Welcome state with a concise greeting and three quick issue chips.
- Full conversation timeline with user and assistant bubbles.
- Visible agent progress steps while a tool is being simulated.
- Structured cards for active rental, billing details, nearby stations, and issue tickets.
- Fixed composer above the device safe area, with virtual-keyboard-friendly spacing.

## Visual direction

Use a calm digital-wellness-inspired mobile style adapted for operational customer service. The feeling is fresh after rain: soft daylight, clean surfaces, low visual noise, and reassuring status feedback. Do not use a landing-page hero, glassmorphism, neon colors, dark mode, decorative cursive fonts, heavy grain, or oversized headings.

### Color tokens

- Canvas: `#F4F7F9`
- Surface: `#FFFFFF`
- Soft blue surface: `#EAF4FF`
- Brand blue: `#2F80ED`
- Brand blue pressed: `#236BC8`
- Umbrella teal: `#22A89A`
- Success: `#16866E`
- Warning: `#E79A2D`
- Error: `#D85656`
- Primary text: `#17212B`
- Secondary text: `#5E6B78`
- Muted text: `#8C98A4`
- Divider: `#E5EBF0`

Use blue for primary actions and AI identity, teal for successful operational states, amber only for warnings, and red only for genuine failures. Never use purple or pink gradients.

### Typography

- Font stack: `Inter`, `PingFang SC`, `Microsoft YaHei`, system sans-serif.
- Page title: 17px / 24px, 650 weight.
- Assistant greeting: 22px / 30px, 680 weight.
- Body and message text: 15px / 23px, 400–500 weight.
- Labels: 12px / 18px, 500–600 weight.
- Numeric values: tabular numerals where supported.

Chinese copy uses sentence case and natural service language. Avoid technical terms such as Tool Calling, Agent Runtime, RAG, or SSE in customer-facing text.

### Shape and depth

- Main cards: 18–22px radius.
- Message bubbles: 18px radius with one reduced corner indicating the speaker.
- Quick actions: 16px radius with light border and subtle colored icon tile.
- Composer: 22px radius, visually floating 8px above the safe area.
- Borders: 1px `#E5EBF0`.
- Shadows: soft and restrained, e.g. `0 10px 30px rgba(31, 65, 94, 0.08)`.
- Do not use thick shadows or glossy effects.

## Layout

- Full viewport uses `100dvh`; no marketing navigation or footer.
- Header height around 58px with `env(safe-area-inset-top)` support.
- Conversation has 16px side padding and 20–24px vertical section gaps.
- User bubble max width 78%, aligned right, solid brand blue with white text.
- Assistant content max width 88%, aligned left. Plain replies use a white bubble; structured results use full-width cards.
- Composer occupies the bottom safe area; message list has matching bottom padding.

## Components

### Service header

Use a compact rounded-square umbrella/support mark built from a simple icon, not an invented brand logo. Show “公共雨伞智能客服” and a small green dot with “AI 在线”。The history action is an icon button with a large touch target.

### Welcome and quick issues

Start with a short assistant welcome. Beneath it show three equal-priority quick actions:

- 还伞失败
- 计费问题
- 附近网点

Each item includes a small functional icon and one-line helper text. They should look like service shortcuts, not promotional cards.

### Streaming state

During the demo, append text character by character inside the assistant bubble. Before text begins, show a compact three-step status strip such as “正在识别问题 → 查询租借记录 → 整理处理建议”. The active step has a blue spinner, complete steps have teal checks, and later steps are muted. Status changes should not cause layout jumps.

### Business cards

- Active rental: status, start time, current fee, station, and a safe next action.
- Billing: order ID, time range, line items, verified total, and “金额来自业务记录” note.
- Nearby station: name, distance, available umbrellas, return docks, freshness timestamp, and primary action.
- Ticket: ticket ID, category, created time, and pending state; do not imply a human is currently online.

### Composer

Single-line input that grows to four lines, a disabled/active circular send button, and no attachment or voice controls in the first draft. Placeholder: “请描述你遇到的问题”. Pressing Enter on desktop sends; on mobile the button is primary.

## Motion

- Streaming character cadence around 18–28ms with natural punctuation pauses.
- New messages rise 6px and fade in over 180ms.
- Status transitions crossfade over 160ms.
- Buttons use 120ms pressed feedback and no bouncy animation.
- Respect reduced-motion preferences by rendering the final text immediately and removing movement.

## Accessibility and interaction

- Minimum touch target: 44 x 44px.
- Text/background contrast must meet WCAG AA.
- Streaming content uses an appropriate live region without announcing every individual character.
- Preserve scroll position while loading old messages; auto-scroll only when the user is already near the bottom.
- A dropped stream displays a retry action and reuses the same request identity.

## Draft content

The initial visual should show a realistic return-failure conversation:

1. Welcome and quick actions near the top of the visible history.
2. User message: “雨伞已经插回去了，为什么订单还在计费？”
3. AI status indicating it is checking the active rental and return station.
4. A partially streamed answer explaining that the return record has not yet been confirmed.
5. A structured active-rental card and a safe instruction to press the lock firmly, wait for the confirmation tone, or use a nearby station with available docks.

Use ONLY the fonts, colors, spacing, and component styles defined in this design system. Do not introduce any fonts, colors, gradients, or visual styles not defined here.
