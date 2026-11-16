import { useMockSupportStream } from "@/hooks/useMockSupportStream"

import { ChatComposer } from "./ChatComposer"
import { MessageList } from "./MessageList"
import { QuickActions } from "./QuickActions"
import { ServiceHeader } from "./ServiceHeader"

export function ChatScreen() {
  const { messages, isStreaming, sendMessage, stopStreaming, reset } = useMockSupportStream()
  const hasMessages = messages.length > 0

  return (
    <div className="app-backdrop flex min-h-[100dvh] items-center justify-center sm:p-5">
      <main className="relative flex h-[100dvh] w-full max-w-[430px] flex-col overflow-hidden bg-background shadow-soft sm:h-[min(844px,calc(100dvh-40px))] sm:rounded-[34px] sm:border-[7px] sm:border-white/50 sm:ring-1 sm:ring-black/5">
        <ServiceHeader hasMessages={hasMessages} onReset={reset} />

        {hasMessages ? (
          <MessageList messages={messages} />
        ) : (
          <div className="chat-scroll flex-1 overflow-y-auto px-4 pb-[108px] pt-6">
            <QuickActions disabled={isStreaming} onSelect={sendMessage} />
            <DemoHint />
          </div>
        )}

        <ChatComposer isStreaming={isStreaming} onSend={sendMessage} onStop={stopStreaming} />
      </main>
    </div>
  )
}

function DemoHint() {
  return (
    <div className="mt-5 rounded-2xl border border-dashed border-[#cfd8df] px-4 py-3 text-xs leading-5 text-[#6f7c88]">
      当前为前端交互演示：点击快捷问题或输入内容，即可查看 AI 查询进度、逐字回复与业务卡片。
    </div>
  )
}
