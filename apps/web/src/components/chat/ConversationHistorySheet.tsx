import { Clock3, MapPin, MessageCircleMore, Plus, ReceiptText, UmbrellaOff } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import type { Conversation } from "@/types/chat"

interface ConversationHistorySheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  conversations: Conversation[]
  activeConversationId: string | null
  disabled: boolean
  onCreate: () => Promise<string | null>
  onSelect: (conversationId: string) => Promise<void>
}

export function ConversationHistorySheet({
  open,
  onOpenChange,
  conversations,
  activeConversationId,
  disabled,
  onCreate,
  onSelect,
}: ConversationHistorySheetProps) {
  const today = conversations.filter((conversation) => isToday(conversation.updatedAt))
  const earlier = conversations.filter((conversation) => !isToday(conversation.updatedAt))

  const create = async () => {
    const id = await onCreate()
    if (id) onOpenChange(false)
  }

  const select = async (id: string) => {
    await onSelect(id)
    onOpenChange(false)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader className="safe-top border-b border-border px-5 pb-4 pt-4 pr-16">
          <SheetTitle>历史会话</SheetTitle>
          <SheetDescription>继续之前的问题，或开始新的咨询。</SheetDescription>
        </SheetHeader>

        <div className="px-4 py-4">
          <Button className="h-11 w-full rounded-xl shadow-none" onClick={create} disabled={disabled}>
            <Plus className="size-[18px]" />
            新建会话
          </Button>
        </div>

        <div className="chat-scroll flex-1 overflow-y-auto px-3 pb-[max(20px,env(safe-area-inset-bottom,20px))]">
          {conversations.length === 0 ? (
            <div className="flex h-48 flex-col items-center justify-center text-center text-sm text-[#8c98a4]">
              <MessageCircleMore className="mb-3 size-8 text-[#b1bac2]" />
              还没有历史会话
            </div>
          ) : null}
          <ConversationGroup
            title="今天"
            conversations={today}
            activeConversationId={activeConversationId}
            disabled={disabled}
            onSelect={select}
          />
          <ConversationGroup
            title="更早"
            conversations={earlier}
            activeConversationId={activeConversationId}
            disabled={disabled}
            onSelect={select}
          />
        </div>
      </SheetContent>
    </Sheet>
  )
}

function ConversationGroup({
  title,
  conversations,
  activeConversationId,
  disabled,
  onSelect,
}: {
  title: string
  conversations: Conversation[]
  activeConversationId: string | null
  disabled: boolean
  onSelect: (id: string) => void
}) {
  if (conversations.length === 0) return null
  return (
    <section className="mb-4">
      <h3 className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8c98a4]">{title}</h3>
      <div className="space-y-1">
        {conversations.map((conversation) => {
          const active = conversation.id === activeConversationId
          const Icon = iconForConversation(conversation.title)
          return (
            <button
              type="button"
              key={conversation.id}
              disabled={disabled}
              onClick={() => onSelect(conversation.id)}
              className={`relative flex min-h-[72px] w-full items-start gap-3 rounded-2xl px-3 py-3 text-left transition-colors disabled:opacity-60 ${
                active ? "bg-[#eaf4ff]" : "hover:bg-[#f4f7f9] active:bg-[#edf2f5]"
              }`}
            >
              {active ? <span className="absolute inset-y-3 left-0 w-[3px] rounded-full bg-primary" /> : null}
              <span
                className={`mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl ${
                  active ? "bg-white text-primary" : "bg-[#f4f7f9] text-[#5e6b78]"
                }`}
              >
                <Icon className="size-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-foreground">{conversation.title}</span>
                  <span className="shrink-0 text-[10px] text-[#8c98a4]">{formatTime(conversation.updatedAt)}</span>
                </span>
                <span className="mt-1 line-clamp-1 block text-xs leading-[18px] text-[#6f7c88]">{conversation.preview}</span>
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}

function iconForConversation(title: string) {
  if (/计费|费用|扣费/.test(title)) return ReceiptText
  if (/附近|网点|位置/.test(title)) return MapPin
  if (/还伞|插回|伞桩/.test(title)) return UmbrellaOff
  return Clock3
}

function isToday(value: string) {
  const date = new Date(value)
  const now = new Date()
  return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate()
}

function formatTime(value: string) {
  const date = new Date(value)
  if (isToday(value)) return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false })
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" })
}
