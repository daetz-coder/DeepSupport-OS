import type { RunOverview, StageBucket, TodoItem, TraceStep } from '../types'

const SKILL_PATH_RE = /\/skills\/(?:imported\/)?([^/]+)\//i

const KNOWLEDGE_TOOLS = new Set(['search_docs', 'search_cases', 'search_knowledge'])
const FS_TOOLS = new Set([
  'read_file',
  'write_file',
  'edit_file',
  'ls',
  'glob',
  'grep',
  'execute',
  'task',
])

function argsDict(args: unknown): Record<string, unknown> {
  if (args && typeof args === 'object' && !Array.isArray(args)) {
    return args as Record<string, unknown>
  }
  if (typeof args === 'string') {
    try {
      const parsed = JSON.parse(args)
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : {}
    } catch {
      return {}
    }
  }
  return {}
}

function pathFromArgs(args: unknown): string {
  const d = argsDict(args)
  return String(d.file_path || d.path || d.filename || '')
}

function skillFromPath(path: string): string | undefined {
  const m = SKILL_PATH_RE.exec(path.replace(/\\/g, '/'))
  return m?.[1]
}

function lookupSource(name: string): { source: string; server?: string } {
  if (KNOWLEDGE_TOOLS.has(name)) return { source: 'knowledge' }
  if (FS_TOOLS.has(name)) return { source: 'filesystem' }
  if (name === 'ask_user') return { source: 'dialogue' }
  if (name === 'run_sandbox_shell') return { source: 'sandbox' }
  return { source: 'local' }
}

/** Ensure SSE steps carry skill_used / tool_source even if a field was omitted. */
export function enrichStep(raw: TraceStep): TraceStep {
  const step = { ...raw }
  const name = String(step.name || '')
  let path = ''
  if (name === 'read_file' || name === 'write_file' || name === 'edit_file') {
    path = pathFromArgs(step.args)
  }
  if (!path && step.offload_path) path = String(step.offload_path)
  if (!step.skill_used && path) {
    const skill = skillFromPath(path)
    if (skill) step.skill_used = skill
  }
  if (
    name &&
    !step.tool_source &&
    (step.kind === 'tool_call' ||
      step.kind === 'subagent_dispatch' ||
      step.kind === 'context_offload' ||
      step.kind === 'tool_result')
  ) {
    const prov = lookupSource(name)
    step.tool_source = prov.source
    if (prov.server) step.mcp_server = prov.server
  }
  if (step.kind === 'tool_call' && name === 'task' && !step.subagent) {
    const args = argsDict(step.args)
    step.kind = 'subagent_dispatch'
    step.subagent = String(args.subagent_type || args.name || args.agent || 'unknown')
  }
  return step
}

function groupStages(steps: TraceStep[]): StageBucket[] {
  const order = [
    ['plan', '理解与规划'],
    ['diagnose', '环境诊断'],
    ['research', '知识检索'],
    ['action', '方案与写操作'],
    ['other', '其他'],
  ] as const
  const buckets = new Map<string, TraceStep[]>()
  for (const s of steps) {
    const id = String(s.stage || 'other')
    const list = buckets.get(id) || []
    list.push(s)
    buckets.set(id, list)
  }
  const out: StageBucket[] = []
  for (const [id, label] of order) {
    const items = buckets.get(id)
    if (!items?.length) continue
    const toolCount = items.filter((s) =>
      ['tool_call', 'subagent_dispatch', 'context_offload', 'tool_result'].includes(s.kind),
    ).length
    out.push({
      id,
      label,
      status: 'running',
      step_count: items.length,
      tool_count: toolCount,
      steps: items,
    })
  }
  return out
}

/** Build a current-run overview from streamed SSE steps + todos. */
export function buildLiveOverview(
  steps: TraceStep[],
  todos: TodoItem[],
  status?: string,
): RunOverview {
  const scoped = steps.map(enrichStep)
  const agents: string[] = []
  const skills: string[] = []
  const toolCounts: Record<string, number> = {}
  const sources: Record<string, number> = {}
  const mcpServers = new Set<string>()

  for (const s of scoped) {
    if (s.kind === 'subagent_dispatch') {
      const sub = String(s.subagent || 'unknown')
      if (!agents.includes(sub)) agents.push(sub)
    }
    if (s.skill_used) {
      const sk = String(s.skill_used)
      if (!skills.includes(sk)) skills.push(sk)
    }
    if (
      s.kind === 'tool_call' ||
      s.kind === 'subagent_dispatch' ||
      s.kind === 'context_offload'
    ) {
      const name = String(s.name || 'unknown')
      toolCounts[name] = (toolCounts[name] || 0) + 1
      const src = String(s.tool_source || 'unknown')
      sources[src] = (sources[src] || 0) + 1
      if (s.mcp_server) mcpServers.add(String(s.mcp_server))
    }
  }

  const completed = todos.filter((t) => t.status === 'completed').length
  const items = Object.entries(toolCounts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))

  return {
    status,
    scope: 'live',
    plan: {
      total: todos.length,
      completed,
      items: todos,
    },
    stages: groupStages(scoped),
    agents,
    skills,
    mcp: {
      local_calls: sources.local || 0,
      remote_calls: sources.remote || 0,
      knowledge_calls: sources.knowledge || 0,
      servers: [...mcpServers].sort(),
      by_source: sources,
    },
    tools: {
      total_calls: items.reduce((n, t) => n + t.count, 0),
      unique: items.length,
      items,
    },
    step_count: scoped.length,
  }
}

function mergeToolItems(
  a: { name: string; count: number }[] = [],
  b: { name: string; count: number }[] = [],
) {
  const map = new Map<string, number>()
  for (const t of [...a, ...b]) {
    map.set(t.name, (map.get(t.name) || 0) + t.count)
  }
  return [...map.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((x, y) => y.count - x.count || x.name.localeCompare(y.name))
}

function unionStrings(a: string[] = [], b: string[] = []) {
  const out: string[] = []
  for (const x of [...a, ...b]) {
    if (x && !out.includes(x)) out.push(x)
  }
  return out
}

/** Merge frozen thread cumulative + live current-run delta. */
export function mergeOverviews(
  baseline: RunOverview | null | undefined,
  live: RunOverview,
): RunOverview {
  if (!baseline) return live

  const toolItems = mergeToolItems(baseline.tools?.items, live.tools?.items)
  const bySource: Record<string, number> = {
    ...(baseline.mcp?.by_source || {}),
  }
  for (const [k, v] of Object.entries(live.mcp?.by_source || {})) {
    bySource[k] = (bySource[k] || 0) + v
  }

  return {
    ...baseline,
    status: live.status || baseline.status,
    scope: 'full_thread+live',
    plan: live.plan?.items?.length ? live.plan : baseline.plan,
    stages: live.stages?.length ? live.stages : baseline.stages,
    agents: unionStrings(baseline.agents, live.agents),
    skills: unionStrings(baseline.skills, live.skills),
    mcp: {
      local_calls: (baseline.mcp?.local_calls || 0) + (live.mcp?.local_calls || 0),
      remote_calls: (baseline.mcp?.remote_calls || 0) + (live.mcp?.remote_calls || 0),
      knowledge_calls:
        (baseline.mcp?.knowledge_calls || 0) + (live.mcp?.knowledge_calls || 0),
      servers: unionStrings(baseline.mcp?.servers, live.mcp?.servers),
      by_source: bySource,
    },
    tools: {
      total_calls: toolItems.reduce((n, t) => n + t.count, 0),
      unique: toolItems.length,
      items: toolItems,
    },
    step_count: (baseline.step_count || 0) + (live.step_count || 0),
    run_step_count: live.step_count,
    thread_duration_ms: baseline.thread_duration_ms,
    duration_ms: baseline.duration_ms,
    run_count: baseline.run_count,
  }
}
