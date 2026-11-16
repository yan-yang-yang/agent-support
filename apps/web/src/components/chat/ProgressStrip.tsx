import { CheckCircle2, LoaderCircle } from "lucide-react"

import type { ProgressStep } from "@/types/chat"

interface ProgressStripProps {
  steps: ProgressStep[]
}

export function ProgressStrip({ steps }: ProgressStripProps) {
  return (
    <div className="overflow-x-auto px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <div className="inline-flex min-w-max items-center rounded-full border border-border bg-white/80 px-3 py-1.5 text-xs font-medium shadow-sm backdrop-blur-sm">
        {steps.map((step, index) => (
          <div key={step.label} className="flex items-center">
            <span
              className={`mr-1.5 flex items-center ${
                step.state === "complete"
                  ? "text-[#16866e]"
                  : step.state === "active"
                    ? "text-primary"
                    : "text-[#a5afb8]"
              }`}
            >
              {step.state === "complete" ? (
                <CheckCircle2 className="size-3.5" />
              ) : step.state === "active" ? (
                <LoaderCircle className="size-3.5 animate-spin" />
              ) : (
                <span className="size-2 rounded-full border border-current" />
              )}
            </span>
            <span className={step.state === "active" ? "text-foreground" : "text-[#6f7c88]"}>{step.label}</span>
            {index < steps.length - 1 ? <span className="mx-2 text-[9px] text-[#a5afb8]">→</span> : null}
          </div>
        ))}
      </div>
    </div>
  )
}
