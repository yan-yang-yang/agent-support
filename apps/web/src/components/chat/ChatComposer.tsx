import { useEffect, useRef, useState } from "react"
import { SendHorizontal, Square } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

interface ChatComposerProps {
  disabled?: boolean
  isStreaming: boolean
  onSend: (value: string) => void
  onStop: () => void
}

export function ChatComposer({ disabled = false, isStreaming, onSend, onStop }: ChatComposerProps) {
  const [value, setValue] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = "auto"
    textarea.style.height = `${Math.min(textarea.scrollHeight, 92)}px`
  }, [value])

  const submit = () => {
    const nextValue = value.trim()
    if (!nextValue || isStreaming || disabled) return
    setValue("")
    onSend(nextValue)
  }

  return (
    <div className="composer-fade pointer-events-none absolute inset-x-0 bottom-0 z-30 px-3 pb-[max(12px,env(safe-area-inset-bottom,12px))] pt-8">
      <div className="pointer-events-auto flex items-end gap-2 rounded-[22px] border border-border bg-white py-2 pl-4 pr-2.5 shadow-[0_-4px_20px_rgba(31,65,94,0.06)]">
        <Textarea
          ref={textareaRef}
          rows={1}
          value={value}
          disabled={isStreaming || disabled}
          maxLength={500}
          placeholder={isStreaming ? "正在处理，请稍候…" : disabled ? "正在加载会话…" : "请描述你遇到的问题"}
          aria-label="输入问题"
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault()
              submit()
            }
          }}
        />
        {isStreaming ? (
          <Button
            type="button"
            size="icon"
            onClick={onStop}
            aria-label="停止生成"
            className="mb-0.5 size-9 shrink-0 rounded-full bg-foreground text-white hover:bg-foreground/90"
          >
            <Square className="size-3.5 fill-current" />
          </Button>
        ) : (
          <Button
            type="button"
            size="icon"
            onClick={submit}
            disabled={!value.trim() || disabled}
            aria-label="发送"
            className="mb-0.5 size-9 shrink-0 rounded-full disabled:bg-[#e5ebf0] disabled:text-[#8c98a4]"
          >
            <SendHorizontal className="size-[18px]" />
          </Button>
        )}
      </div>
    </div>
  )
}
