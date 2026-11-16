import type { BusinessCardData, ChatMessage, Conversation } from "@/types/chat"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1"
const DEMO_USER_ID = "demo-user"

interface ConversationWire {
  id: string
  title: string
  preview: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface MessageWire {
  id: string
  conversation_id: string
  role: "user" | "assistant"
  content: string
  created_at: string
  card: BusinessCardData | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Demo-User": DEMO_USER_ID,
      ...init?.headers,
    },
  })
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`)
  }
  return (await response.json()) as T
}

export function mapConversation(value: ConversationWire): Conversation {
  return {
    id: value.id,
    title: value.title,
    preview: value.preview,
    createdAt: value.created_at,
    updatedAt: value.updated_at,
    messageCount: value.message_count,
  }
}

export function mapMessage(value: MessageWire): ChatMessage {
  return {
    id: value.id,
    role: value.role,
    content: value.content,
    createdAt: value.created_at,
    card: value.card ?? undefined,
  }
}

export async function listConversations(): Promise<Conversation[]> {
  return (await request<ConversationWire[]>("/conversations")).map(mapConversation)
}

export async function createConversation(): Promise<Conversation> {
  return mapConversation(
    await request<ConversationWire>("/conversations", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  )
}

export async function listMessages(conversationId: string): Promise<ChatMessage[]> {
  return (await request<MessageWire[]>(`/conversations/${conversationId}/messages`)).map(mapMessage)
}

export { API_BASE_URL, DEMO_USER_ID }
