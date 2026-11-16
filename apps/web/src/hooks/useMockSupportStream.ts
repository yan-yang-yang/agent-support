import { useCallback, useRef, useState } from "react"

import type { ChatMessage, ProgressStep, Scenario, StreamScript } from "@/types/chat"

const scripts: Record<Scenario, StreamScript> = {
  return: {
    scenario: "return",
    progressLabels: ["识别还伞问题", "查询租借记录", "整理处理建议"],
    response:
      "我查到了你当前有一笔进行中的订单，系统暂时还没有收到有效的还伞确认。请先确认雨伞已推到底并听到提示音；如果当前伞桩已满，可以前往下方有空位的附近网点。",
    card: {
      kind: "rental",
      startedAt: "今日 08:30",
      station: "地铁 1 号线科技园站 A 口",
      fee: "¥3.00",
      status: "计费中",
    },
  },
  billing: {
    scenario: "billing",
    progressLabels: ["识别计费问题", "核对订单明细", "整理费用说明"],
    response:
      "我已经核对了最近一笔订单。当前总费用由基础使用费和超时费组成，金额与业务记录一致。如果你仍有异议，我可以继续为这笔订单创建待处理工单。",
    card: {
      kind: "billing",
      orderId: "US202611160083",
      duration: "42 分钟",
      baseFee: "¥2.00",
      overtimeFee: "¥1.00",
      total: "¥3.00",
    },
  },
  nearby: {
    scenario: "nearby",
    progressLabels: ["识别网点需求", "查询附近网点", "筛选可用位置"],
    response: "我找到了 2 个可以正常还伞的附近网点，库存和空位可能会实时变化，建议优先前往距离最近的科技园站 B 口。",
    card: {
      kind: "stations",
      stations: [
        { name: "科技园站 B 口", distance: "180m", umbrellas: 6, docks: 4 },
        { name: "文三路园区南门", distance: "420m", umbrellas: 3, docks: 7 },
      ],
    },
  },
}

function detectScenario(text: string): Scenario {
  if (/附近|网点|哪里|位置|借伞/.test(text)) return "nearby"
  if (/还伞|插回|伞桩|还不了|归还/.test(text)) return "return"
  if (/费用|扣费|计费|退款|金额/.test(text)) return "billing"
  return "return"
}

function buildSteps(labels: StreamScript["progressLabels"], activeIndex: number): ProgressStep[] {
  return labels.map((label, index) => ({
    label,
    state: index < activeIndex ? "complete" : index === activeIndex ? "active" : "pending",
  }))
}

function wait(duration: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(resolve, duration)
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timer)
        reject(new DOMException("Streaming aborted", "AbortError"))
      },
      { once: true },
    )
  })
}

export function useMockSupportStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const activeController = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (rawText: string) => {
    const text = rawText.trim()
    if (!text || activeController.current) return

    const controller = new AbortController()
    activeController.current = controller
    setIsStreaming(true)

    const scenario = detectScenario(text)
    const script = scripts[scenario]
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text }
    const assistantId = crypto.randomUUID()
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      streaming: true,
      progress: buildSteps(script.progressLabels, 0),
    }

    setMessages((current) => [...current, userMessage, assistantMessage])

    try {
      await wait(520, controller.signal)
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId ? { ...message, progress: buildSteps(script.progressLabels, 1) } : message,
        ),
      )

      await wait(720, controller.signal)
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId ? { ...message, progress: buildSteps(script.progressLabels, 2) } : message,
        ),
      )

      for (let index = 0; index < script.response.length; index += 1) {
        const character = script.response[index]
        const punctuationPause = /[，。；！]/.test(character) ? 110 : 0
        await wait(22 + punctuationPause, controller.signal)
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId ? { ...message, content: script.response.slice(0, index + 1) } : message,
          ),
        )
      }

      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                streaming: false,
                progress: buildSteps(script.progressLabels, 3),
                card: script.card,
              }
            : message,
        ),
      )
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) throw error
    } finally {
      activeController.current = null
      setIsStreaming(false)
    }
  }, [])

  const stopStreaming = useCallback(() => {
    activeController.current?.abort()
    activeController.current = null
    setIsStreaming(false)
    setMessages((current) =>
      current.map((message) =>
        message.streaming
          ? {
              ...message,
              content: message.content || "已停止生成。",
              streaming: false,
              progress: undefined,
            }
          : message,
      ),
    )
  }, [])

  const reset = useCallback(() => {
    activeController.current?.abort()
    activeController.current = null
    setIsStreaming(false)
    setMessages([])
  }, [])

  return { messages, isStreaming, sendMessage, stopStreaming, reset }
}
