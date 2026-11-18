import { useCallback, useEffect, useRef, useState } from "react"

import { ensureSupportSession, type AuthUser } from "@/api/auth"
import { createConversation, listConversations, listMessages, mapMessage } from "@/api/client"
import { streamMessage, type SupportStreamEvent } from "@/api/sse"
import type { ChatMessage, Conversation } from "@/types/chat"

export function useSupportChat() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null)
  const activeController = useRef<AbortController | null>(null)

  const refreshConversations = useCallback(async () => {
    const next = await listConversations()
    setConversations(next)
    return next
  }, [])

  const selectConversation = useCallback(async (conversationId: string) => {
    activeController.current?.abort()
    activeController.current = null
    setIsStreaming(false)
    setIsLoading(true)
    setError(null)
    try {
      const history = await listMessages(conversationId)
      setActiveConversationId(conversationId)
      setMessages(history)
    } catch {
      setError("历史消息加载失败，请稍后重试。")
    } finally {
      setIsLoading(false)
    }
  }, [])

  const newConversation = useCallback(async () => {
    activeController.current?.abort()
    activeController.current = null
    setIsStreaming(false)
    setIsLoading(true)
    setError(null)
    try {
      const conversation = await createConversation()
      setConversations((current) => [conversation, ...current])
      setActiveConversationId(conversation.id)
      setMessages([])
      return conversation.id
    } catch {
      setError("新会话创建失败，请确认后端服务已启动。")
      return null
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const initialize = async () => {
      setIsLoading(true)
      try {
        const identity = await ensureSupportSession()
        if (cancelled) return
        setCurrentUser(identity)
        let history = await listConversations()
        if (cancelled) return
        if (history.length === 0) {
          const conversation = await createConversation()
          history = [conversation]
        }
        if (cancelled) return
        setConversations(history)
        setActiveConversationId(history[0].id)
        setMessages(await listMessages(history[0].id))
      } catch {
        if (!cancelled) setError("身份校验失败，请从公共雨伞业务入口重新进入客服。")
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }
    void initialize()
    return () => {
      cancelled = true
      activeController.current?.abort()
    }
  }, [])

  const sendMessage = useCallback(
    async (rawText: string) => {
      const content = rawText.trim()
      if (!content || isStreaming) return

      let conversationId = activeConversationId
      if (!conversationId) conversationId = await newConversation()
      if (!conversationId) return

      const requestId = crypto.randomUUID()
      const userTempId = `user-${requestId}`
      const assistantTempId = `assistant-${requestId}`
      const controller = new AbortController()
      activeController.current = controller
      setIsStreaming(true)
      setError(null)
      setMessages((current) => [
        ...current,
        { id: userTempId, role: "user", content },
        { id: assistantTempId, role: "assistant", content: "", streaming: true },
      ])

      const onEvent = (event: SupportStreamEvent) => {
        if (event.type === "message.started") {
          const persistedUser = mapMessage(event.data.message)
          setMessages((current) => current.map((message) => (message.id === userTempId ? persistedUser : message)))
          return
        }
        if (event.type === "progress.updated") {
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantTempId ? { ...message, progress: event.data.steps } : message,
            ),
          )
          return
        }
        if (event.type === "assistant.delta") {
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantTempId
                ? { ...message, content: `${message.content}${event.data.delta}` }
                : message,
            ),
          )
          return
        }
        if (event.type === "business_card") {
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantTempId ? { ...message, card: event.data.card } : message,
            ),
          )
          return
        }
        if (event.type === "assistant.completed") {
          const persistedAssistant = mapMessage(event.data.message)
          setMessages((current) =>
            current.map((message) => (message.id === assistantTempId ? persistedAssistant : message)),
          )
        }
      }

      try {
        await streamMessage({ conversationId, content, requestId, signal: controller.signal, onEvent })
        await refreshConversations()
      } catch (streamError) {
        if (!(streamError instanceof DOMException && streamError.name === "AbortError")) {
          setError("流式连接中断，请稍后重试。")
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantTempId
                ? { ...message, content: message.content || "连接中断，请稍后重试。", streaming: false, progress: undefined }
                : message,
            ),
          )
        }
      } finally {
        activeController.current = null
        setIsStreaming(false)
        setMessages((current) =>
          current.map((message) => (message.id === assistantTempId ? { ...message, streaming: false } : message)),
        )
      }
    },
    [activeConversationId, isStreaming, newConversation, refreshConversations],
  )

  const stopStreaming = useCallback(() => {
    activeController.current?.abort()
    activeController.current = null
    setIsStreaming(false)
    setMessages((current) =>
      current.map((message) =>
        message.streaming
          ? { ...message, content: message.content || "已停止生成。", streaming: false, progress: undefined }
          : message,
      ),
    )
  }, [])

  return {
    conversations,
    activeConversationId,
    messages,
    isLoading,
    isStreaming,
    error,
    currentUser,
    sendMessage,
    stopStreaming,
    selectConversation,
    newConversation,
    refreshConversations,
  }
}
