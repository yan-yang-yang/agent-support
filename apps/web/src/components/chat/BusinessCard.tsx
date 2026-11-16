import { Clock3, Info, MapPin, Navigation, ReceiptText } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import type { BusinessCardData } from "@/types/chat"

interface BusinessCardProps {
  data: BusinessCardData
}

export function BusinessCard({ data }: BusinessCardProps) {
  if (data.kind === "rental") {
    return (
      <Card className="animate-message-in">
        <CardContent>
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Clock3 className="size-4 text-[#e79a2d]" />
              进行中订单
            </div>
            <span className="rounded-md bg-[#fff4e5] px-2 py-0.5 text-xs font-medium text-[#d58716]">{data.status}</span>
          </div>
          <dl className="space-y-2.5 text-sm">
            <DataRow label="借出时间" value={data.startedAt} mono />
            <DataRow label="借出网点" value={data.station} />
            <DataRow label="当前费用" value={data.fee} strong mono />
          </dl>
          <div className="my-3 h-px bg-border" />
          <div className="flex items-start gap-2.5 rounded-xl bg-[#eaf4ff] p-3 text-[13px] font-medium leading-[19px]">
            <Info className="mt-0.5 size-4 shrink-0 text-primary" />
            <span>请用力推入伞桩并等待提示音；若当前网点已满，可查询附近有空位的网点。</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (data.kind === "billing") {
    return (
      <Card className="animate-message-in">
        <CardContent>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <ReceiptText className="size-4 text-primary" />
            计费明细
          </div>
          <div className="mb-3 rounded-xl bg-[#f4f7f9] px-3 py-2 text-xs text-[#5e6b78]">
            订单号 <span className="font-mono text-foreground">{data.orderId}</span> · 使用 {data.duration}
          </div>
          <dl className="space-y-2.5 text-sm">
            <DataRow label="基础使用费" value={data.baseFee} mono />
            <DataRow label="超时费" value={data.overtimeFee} mono />
            <div className="h-px bg-border" />
            <DataRow label="合计" value={data.total} strong mono />
          </dl>
          <p className="mt-3 text-xs text-[#8c98a4]">金额来自模拟业务记录，AI 不会自行修改账单。</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="animate-message-in space-y-2.5">
      {data.stations.map((station, index) => (
        <Card key={station.name} className={index === 0 ? "border-[#cfe2f8]" : undefined}>
          <CardContent className="flex items-center gap-3 p-3.5">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-[#eaf4ff] text-primary">
              <MapPin className="size-[18px]" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="truncate text-sm font-semibold">{station.name}</p>
                {index === 0 ? <span className="rounded bg-[#e8f7f4] px-1.5 py-0.5 text-[10px] font-semibold text-[#16866e]">最近</span> : null}
              </div>
              <p className="mt-1 text-xs text-[#5e6b78]">
                {station.distance} · 可借 {station.umbrellas} · 可还 {station.docks}
              </p>
            </div>
            <Navigation className="size-[18px] shrink-0 text-primary" />
          </CardContent>
        </Card>
      ))}
      <p className="px-1 text-[11px] text-[#8c98a4]">模拟数据 · 库存更新于刚刚</p>
    </div>
  )
}

function DataRow({ label, value, mono = false, strong = false }: { label: string; value: string; mono?: boolean; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-[13px] text-[#5e6b78]">{label}</dt>
      <dd className={`${mono ? "font-mono" : ""} ${strong ? "text-[15px] font-semibold" : "font-medium"}`}>{value}</dd>
    </div>
  )
}
