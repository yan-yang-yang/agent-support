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

function ErrorHint({ message }: { message: string }) {
  return <div className="mt-5 rounded-2xl border border-[#f0caca] bg-[#fff7f7] px-4 py-3 text-xs leading-5 text-[#b74444]">{message}</div>
}

function ErrorToast({ message }: { message: string }) {
  return (
    <div className="absolute bottom-[92px] left-4 right-4 z-20 rounded-xl border border-[#f0caca] bg-white px-3 py-2 text-center text-xs text-[#b74444] shadow-soft">
      {message}
    </div>
  )
}

function DemoHint() {
  return (
    <div className="mt-5 rounded-2xl border border-dashed border-[#cfd8df] px-4 py-3 text-xs leading-5 text-[#6f7c88]">
      会话记录由本地 FastAPI 保存；点击快捷问题或输入内容，可查看 SSE 查询进度、逐字回复与业务卡片。
    </div>
  )
}
