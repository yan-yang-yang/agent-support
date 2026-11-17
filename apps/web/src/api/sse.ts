import { API_BASE_URL, DEMO_USER_ID, type MessageWire } from "@/api/client"
import type { BusinessCardData, ProgressStep } from "@/types/chat"

export type SupportStreamEvent =
  | { type: "message.started"; data: { requestId: string; assistantId: string; message: MessageWire } }
  | { type: "progress.updated"; data: { steps: ProgressStep[] } }
  | { type: "assistant.delta"; data: { delta: string } }
  | { type: "tool.started"; data: { name: string } }
  | { type: "tool.completed"; data: { name: string; status: string; callId: string; errorCode?: string | null } }
  | { type: "business_card"; data: { card: BusinessCardData } }
  | { type: "assistant.completed"; data: { requestId: string; message: MessageWire } }

interface StreamMessageOptions {
  conversationId: string
  content: string
  requestId: string
  signal: AbortSignal
  onEvent: (event: SupportStreamEvent) => void
}

export async function streamMessage(options: StreamMessageOptions): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/conversations/${options.conversationId}/messages:stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "X-Demo-User": DEMO_USER_ID,
      "X-Request-ID": options.requestId,
    },
    body: JSON.stringify({ content: options.content, request_id: options.requestId }),
    signal: options.signal,
  })

  if (!response.ok || !response.body) {
    throw new Error(`SSE request failed: ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const blocks = buffer.split("\n\n")
    buffer = blocks.pop() ?? ""
    for (const block of blocks) {
      const parsed = parseSseBlock(block)
      if (parsed) options.onEvent(parsed)
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseBlock(buffer)
    if (parsed) options.onEvent(parsed)
  }
}

function parseSseBlock(block: string): SupportStreamEvent | null {
  let eventName = ""
  const dataLines: string[] = []

  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) eventName = line.slice(7)
    if (line.startsWith("data: ")) dataLines.push(line.slice(6))
  }
  if (!eventName || dataLines.length === 0) return null

  return {
    type: eventName,
    data: JSON.parse(dataLines.join("\n")) as unknown,
  } as SupportStreamEvent
}
