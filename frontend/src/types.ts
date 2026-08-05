export type TraceStep = {
  kind: string
  content?: string
  name?: string
  args?: unknown
  id?: string
  tool_call_id?: string
  subagent?: string
}

export type HitlHighlight = { key: string; value: string }
export type HitlPreview = {
  name: string
  label: string
  highlights: HitlHighlight[]
  args: Record<string, unknown>
}

export type InterruptInfo = {
  next?: string[]
  pending_writes?: TraceStep[]
  pending_preview?: HitlPreview[]
  tasks?: string[]
}

export type Trace = {
  steps?: TraceStep[]
  pending_writes?: TraceStep[]
  interrupt?: unknown
}

export type TaskItem = {
  task_id: string
  thread_id: string
  status: string
  updated_at?: string
  preview?: string
}

export type AuditItem = {
  id: number
  task_id: string
  tool: string
  arguments: string
  result: string
  timestamp?: string
}

export type TodoItem = {
  content: string
  status: 'pending' | 'in_progress' | 'completed'
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
