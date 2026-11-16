export type Scenario = "return" | "billing" | "nearby"

export type ProgressState = "pending" | "active" | "complete"

export interface ProgressStep {
  label: string
  state: ProgressState
}

export interface ActiveRentalCardData {
  kind: "rental"
  startedAt: string
  station: string
  fee: string
  status: string
}

export interface BillingCardData {
  kind: "billing"
  orderId: string
  duration: string
  baseFee: string
  overtimeFee: string
  total: string
}

export interface StationCardData {
  kind: "stations"
  stations: Array<{
    name: string
    distance: string
    umbrellas: number
    docks: number
  }>
}

export type BusinessCardData = ActiveRentalCardData | BillingCardData | StationCardData

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  streaming?: boolean
  progress?: ProgressStep[]
  card?: BusinessCardData
}

export interface StreamScript {
  scenario: Scenario
  progressLabels: [string, string, string]
  response: string
  card: BusinessCardData
}
