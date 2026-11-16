# Shared Layouts

## `apps/web/src/components/chat/ChatScreen.tsx`

Full-height mobile H5 shell with persisted conversation state, history drawer, messages, and fixed composer.

```tsx
import { useState } from "react"
import { LoaderCircle } from "lucide-react"

import { useSupportChat } from "@/hooks/useSupportChat"

import { ChatComposer } from "./ChatComposer"
import { ConversationHistorySheet } from "./ConversationHistorySheet"
import { MessageList } from "./MessageList"
import { QuickActions } from "./QuickActions"
import { ServiceHeader } from "./ServiceHeader"

export function ChatScreen() {
  const [historyOpen, setHistoryOpen] = useState(false)
  const {
    conversations,
    activeConversationId,
    messages,
    isLoading,
    isStreaming,
    error,
    sendMessage,
    stopStreaming,
    selectConversation,
    newConversation,
  } = useSupportChat()
  const hasMessages = messages.length > 0

  return (
    <div className="app-backdrop flex min-h-[100dvh] items-center justify-center sm:p-5">
      <main className="relative flex h-[100dvh] w-full max-w-[430px] flex-col overflow-hidden bg-background shadow-soft sm:h-[min(844px,calc(100dvh-40px))] sm:rounded-[34px] sm:border-[7px] sm:border-white/50 sm:ring-1 sm:ring-black/5">
        <ServiceHeader disabled={isStreaming || isLoading} onOpenHistory={() => setHistoryOpen(true)} />

        {isLoading ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-sm text-[#6f7c88]">
            <LoaderCircle className="size-6 animate-spin text-primary" />
            正在加载会话
          </div>
        ) : hasMessages ? (
          <MessageList messages={messages} />
        ) : (
          <div className="chat-scroll flex-1 overflow-y-auto px-4 pb-[108px] pt-6">
            <QuickActions disabled={isStreaming || !activeConversationId} onSelect={sendMessage} />
            {error ? <ErrorHint message={error} /> : <DemoHint />}
          </div>
        )}

        {error && hasMessages ? <ErrorToast message={error} /> : null}
        <ChatComposer
          disabled={isLoading || !activeConversationId}
          isStreaming={isStreaming}
          onSend={sendMessage}
          onStop={stopStreaming}
        />
        <ConversationHistorySheet
          open={historyOpen}
          onOpenChange={setHistoryOpen}
          conversations={conversations}
          activeConversationId={activeConversationId}
          disabled={isLoading || isStreaming}
          onCreate={newConversation}
          onSelect={selectConversation}
        />
      </main>
    </div>
  )
}
```

## `apps/web/src/components/chat/ServiceHeader.tsx`

Compact service identity and history action used at the top of the chat.

```tsx
import { History, Umbrella } from "lucide-react"

import { Button } from "@/components/ui/button"

interface ServiceHeaderProps {
  disabled?: boolean
  onOpenHistory: () => void
}

export function ServiceHeader({ disabled = false, onOpenHistory }: ServiceHeaderProps) {
  return (
    <header className="safe-top z-20 flex min-h-[58px] shrink-0 items-center justify-between border-b border-border bg-white px-4">
      <div className="flex items-center gap-3">
        <div className="flex size-8 items-center justify-center rounded-[10px] bg-primary text-white shadow-sm">
          <Umbrella aria-hidden="true" className="size-[18px]" />
        </div>
        <div>
          <h1 className="text-[15px] font-semibold leading-5 tracking-tight text-foreground">公共雨伞智能客服</h1>
          <div className="flex items-center gap-1.5">
            <span className="size-1.5 rounded-full bg-[#16866e]" aria-hidden="true" />
            <span className="text-[11px] font-medium leading-[14px] text-[#5e6b78]">AI 在线</span>
          </div>
        </div>
      </div>

      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="历史会话"
        onClick={onOpenHistory}
        disabled={disabled}
        className="rounded-full text-[#5e6b78]"
      >
        <History className="size-5" />
      </Button>
    </header>
  )
}
```
