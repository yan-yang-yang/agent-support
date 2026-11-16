# Route Map

The app currently uses a single Vite entry without React Router.

| URL | Entry | Page component | Layout |
| --- | --- | --- | --- |
| `/` | `apps/web/src/main.tsx` | `apps/web/src/App.tsx` → `ChatScreen` | Full-height mobile chat shell |

## Router/entry source

`apps/web/src/App.tsx`

```tsx
import { ChatScreen } from "@/components/chat/ChatScreen"

export default function App() {
  return <ChatScreen />
}
```

`apps/web/src/main.tsx`

```tsx
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import App from "./App"
import "./index.css"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

The `/` page renders the public-umbrella AI chat, quick issue shortcuts, streamed replies, and structured business cards. The requested history feature remains an overlay/drawer within this route rather than a separate route.
