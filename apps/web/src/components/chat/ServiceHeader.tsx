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
