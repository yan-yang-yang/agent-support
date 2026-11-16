import { ChevronRight, MapPin, ReceiptText, UmbrellaOff } from "lucide-react"

interface QuickActionsProps {
  disabled: boolean
  onSelect: (value: string) => void
}

const actions = [
  {
    label: "还伞失败",
    helper: "插回伞桩但仍在计费",
    prompt: "雨伞已经插回去了，为什么订单还在计费？",
    icon: UmbrellaOff,
    primary: true,
  },
  {
    label: "计费问题",
    helper: "对订单扣费金额有疑问",
    prompt: "我对最近一笔订单的计费有疑问",
    icon: ReceiptText,
  },
  {
    label: "附近网点",
    helper: "查找可借还的伞桩位置",
    prompt: "附近哪里有可以还伞的网点？",
    icon: MapPin,
  },
]

export function QuickActions({ disabled, onSelect }: QuickActionsProps) {
  return (
    <section className="animate-message-in space-y-3">
      <div className="px-1">
        <p className="text-[22px] font-bold leading-[30px] tracking-tight text-foreground">你好，我是智能助手。</p>
        <p className="mt-0.5 text-base font-medium text-[#5e6b78]">遇到什么问题了吗？</p>
      </div>

      <div className="space-y-2.5 pt-1">
        {actions.map(({ label, helper, prompt, icon: Icon, primary }) => (
          <button
            key={label}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(prompt)}
            className="group flex w-full items-center gap-3 rounded-2xl border border-border bg-white p-3.5 text-left transition-colors hover:border-[#cfe2f8] hover:bg-[#fbfdff] active:bg-[#f4f7f9] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <span
              className={`flex size-8 shrink-0 items-center justify-center rounded-full ${
                primary ? "bg-[#eaf4ff] text-primary" : "bg-[#f4f7f9] text-[#5e6b78]"
              }`}
            >
              <Icon className="size-[18px]" aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[15px] font-medium leading-5 text-foreground">{label}</span>
              <span className="mt-0.5 block text-xs leading-4 text-[#8c98a4]">{helper}</span>
            </span>
            <ChevronRight className="size-4 shrink-0 text-[#8c98a4] transition-transform group-hover:translate-x-0.5" />
          </button>
        ))}
      </div>
    </section>
  )
}
