import { API_BASE_URL } from "@/api/config"

const DEMO_CLIENT_ID_KEY = "agent-support.demo-client-id"
const DEMO_PROFILES = new Set([
  "demo-user",
  "demo-return-user",
  "demo-billing-user",
  "demo-nearby-user",
])

export interface AuthUser {
  user_id: string
  display_name: string
  source: string
}

let sessionPromise: Promise<AuthUser> | null = null

export function ensureSupportSession(): Promise<AuthUser> {
  sessionPromise ??= initializeSupportSession()
  return sessionPromise
}

async function initializeSupportSession(): Promise<AuthUser> {
  const url = new URL(window.location.href)
  const hashParams = new URLSearchParams(url.hash.slice(1))
  const launchToken = hashParams.get("launch_token") ?? url.searchParams.get("launch_token")
  const requestedProfile = url.searchParams.get("demo_profile")

  if (launchToken) {
    try {
      return await authRequest("/auth/exchange", {
        method: "POST",
        body: JSON.stringify({ launch_token: launchToken }),
      })
    } finally {
      url.searchParams.delete("launch_token")
      hashParams.delete("launch_token")
      url.hash = hashParams.toString()
      replaceBrowserUrl(url)
    }
  }

  if (requestedProfile && DEMO_PROFILES.has(requestedProfile)) {
    try {
      return await createDemoSession(requestedProfile)
    } finally {
      url.searchParams.delete("demo_profile")
      replaceBrowserUrl(url)
    }
  }

  const current = await fetch(`${API_BASE_URL}/auth/me`, {
    credentials: "include",
  })
  if (current.ok) return (await current.json()) as AuthUser
  if (current.status !== 401) throw new Error(`Auth request failed: ${current.status}`)
  return createDemoSession("demo-user")
}

function createDemoSession(profile: string): Promise<AuthUser> {
  return authRequest("/auth/demo-session", {
    method: "POST",
    body: JSON.stringify({ client_id: getDemoClientId(), profile }),
  })
}

async function authRequest(path: string, init: RequestInit): Promise<AuthUser> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  })
  if (!response.ok) throw new Error(`Auth request failed: ${response.status}`)
  return (await response.json()) as AuthUser
}

function getDemoClientId(): string {
  const existing = window.localStorage.getItem(DEMO_CLIENT_ID_KEY)
  if (existing) return existing
  const clientId = crypto.randomUUID()
  window.localStorage.setItem(DEMO_CLIENT_ID_KEY, clientId)
  return clientId
}

function replaceBrowserUrl(url: URL): void {
  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`)
}
