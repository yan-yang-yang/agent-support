import { useEffect, useRef } from "react"

import { BusinessCard } from "@/components/chat/BusinessCard"
import { ProgressStrip } from "@/components/chat/ProgressStrip"
import type { ChatMessage } from "@/types/chat"

interface MessageListProps {
  messages: ChatMessage[]
}

export function MessageList({ messages }: MessageListProps) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const stickToBottomRef = useRef(true)

  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport || !stickToBottomRef.current) return
    viewport.scrollTop = viewport.scrollHeight
  }, [messages])

  return (
    <div
      ref={viewportRef}
      className="chat-scroll flex-1 overflow-y-auto px-4 pb-[108px] pt-5"
      onScroll={(event) => {
        const viewport = event.currentTarget
        stickToBottomRef.current = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 120
      }}
    >
      <div className="space-y-5">
        {messages.map((message) =>
          message.role === "user" ? (
            <div key={message.id} className="flex animate-message-in justify-end">
              <div className="max-w-[78%] rounded-[18px] rounded-br-[4px] bg-primary px-4 py-3 text-[15px] leading-[23px] text-white shadow-sm">
                {message.content}
              </div>
            </div>
          ) : (
            <article key={message.id} className="max-w-[92%] animate-message-in space-y-3" aria-live="off">
              {message.progress ? <ProgressStrip steps={message.progress} /> : null}
              {message.content ? (
                <div className="inline-block rounded-[18px] rounded-bl-[4px] border border-border bg-white px-4 py-3 text-[15px] leading-[23px] text-foreground shadow-sm">
                  {message.content}
                  {message.streaming ? <span className="ml-1 inline-block h-[15px] w-[3px] animate-cursor bg-primary align-middle" /> : null}
                </div>
              ) : (
                <div className="inline-flex items-center gap-1 rounded-[18px] rounded-bl-[4px] border border-border bg-white px-4 py-3 shadow-sm" aria-label="AI 正在处理">
                  <TypingDot delay="0ms" />
                  <TypingDot delay="120ms" />
                  <TypingDot delay="240ms" />
                </div>
              )}
              {message.card ? <BusinessCard data={message.card} /> : null}
              {!message.streaming && message.content ? (
                <span className="sr-only" role="status" aria-live="polite">
                  AI 回复已完成
                </span>
              ) : null}
            </article>
          ),
        )}
      </div>
    </div>
  )
}

function TypingDot({ delay }: { delay: string }) {
  return <span className="size-1.5 animate-bounce rounded-full bg-[#8c98a4]" style={{ animationDelay: delay }} />
}
