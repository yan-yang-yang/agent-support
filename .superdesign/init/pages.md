# Page Dependency Trees

## `/` — Public Umbrella AI Customer Service

Entry: `apps/web/src/App.tsx`

Dependencies:

- `apps/web/src/components/chat/ChatScreen.tsx`
  - `apps/web/src/hooks/useSupportChat.ts`
    - `apps/web/src/api/client.ts`
      - `apps/web/src/types/chat.ts`
    - `apps/web/src/api/sse.ts`
      - `apps/web/src/api/client.ts`
      - `apps/web/src/types/chat.ts`
    - `apps/web/src/types/chat.ts`
  - `apps/web/src/components/chat/ServiceHeader.tsx`
    - `apps/web/src/components/ui/button.tsx`
      - `apps/web/src/lib/utils.ts`
  - `apps/web/src/components/chat/QuickActions.tsx`
  - `apps/web/src/components/chat/ConversationHistorySheet.tsx`
    - `apps/web/src/components/ui/button.tsx`
    - `apps/web/src/components/ui/sheet.tsx`
      - `apps/web/src/lib/utils.ts`
    - `apps/web/src/types/chat.ts`
  - `apps/web/src/components/chat/MessageList.tsx`
    - `apps/web/src/components/chat/ProgressStrip.tsx`
      - `apps/web/src/types/chat.ts`
    - `apps/web/src/components/chat/BusinessCard.tsx`
      - `apps/web/src/components/ui/card.tsx`
        - `apps/web/src/lib/utils.ts`
      - `apps/web/src/types/chat.ts`
  - `apps/web/src/components/chat/ChatComposer.tsx`
    - `apps/web/src/components/ui/button.tsx`
    - `apps/web/src/components/ui/textarea.tsx`
      - `apps/web/src/lib/utils.ts`
- `apps/web/src/index.css`
- `apps/web/tailwind.config.ts`

The page is a single mobile chat shell connected to FastAPI SSE. Its right-side Sheet/Drawer lists persisted conversations and keeps the main chat page visible behind a dimmed overlay.
