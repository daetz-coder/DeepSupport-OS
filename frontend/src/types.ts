export type TraceStep = {
  kind: string
  content?: string
  name?: string
  args?: unknown
  id?: string
  tool_call_id?: string
  subagent?: string
  stage?: string
  skill_used?: string
  tool_source?: string
  mcp_server?: string
  offload_path?: string
}

export type HitlHighlight = { key: string; value: string }
export type HitlPreview = {
  name: string
  label: string
  highlights: HitlHighlight[]
  args: Record<string, unknown>
}

export type InterruptInfo = {
  type?: 'ask' | 'hitl' | string
  question?: string
  context?: string
  next?: string[]
  pending_writes?: TraceStep[]
  pending_preview?: HitlPreview[]
  tasks?: string[]
}

export type Trace = {
  steps?: TraceStep[]
  pending_writes?: TraceStep[]
  stages?: StageBucket[]
  skills_used?: string[]
  interrupt?: unknown
}

export type StageBucket = {
  id: string
  label: string
  status?: string
  step_count: number
  tool_count?: number
  summary?: string
  steps: TraceStep[]
}

export type TodoItem = {
  content: string
  status: 'pending' | 'in_progress' | 'completed'
}

export type RunOverview = {
  status?: string
  duration_ms?: number | null
  thread_duration_ms?: number | null
  run_count?: number
  run_step_count?: number
  scope?: string
  plan?: { total: number; completed: number; items?: TodoItem[] }
  stages?: StageBucket[]
  agents?: string[]
  skills?: string[]
  mcp?: {
    local_calls?: number
    remote_calls?: number
    knowledge_calls?: number
    servers?: string[]
    by_source?: Record<string, number>
  }
  tools?: {
    total_calls?: number
    unique?: number
    items?: { name: string; count: number }[]
  }
  step_count?: number
  thread_step_count?: number
}

export type TaskItem = {
  task_id: string
  thread_id: string
  status: string
  updated_at?: string
  preview?: string
}

export type ThreadRun = {
  task_id: string
  status: string
  updated_at?: string
  preview?: string
}

export type ThreadItem = {
  thread_id: string
  run_count: number
  latest_status: string
  updated_at?: string
  preview?: string
  latest_task_id: string
  runs?: ThreadRun[]
}

export type ChatMessage = {
  role: string
  content?: string
  tool_calls?: unknown[]
  name?: string
}

export type ChatBubble = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  pendingAsk?: boolean
}

export type AuditItem = {
  id: number
  task_id: string
  tool: string
  arguments: string
  result: string
  timestamp?: string
}

export type ArtifactItem = {
  name: string
  path: string
  bytes: number
  canonical?: boolean
  preview?: string
  updated_at?: string
}

export type SkillItem = {
  name: string
  dir_name: string
  description: string
  path: string
  layer: string
  enabled: boolean
  has_references?: boolean
}

export type CatalogEntry = {
  id: string
  name: string
  description?: string
  license?: string
  install?: string
  url?: string
  optional?: boolean
  source?: string
}

export type McpServerSpec = {
  enabled: boolean
  transport?: string
  url?: string
  command?: string
  description?: string
}
