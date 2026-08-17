<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { API, apiHeaders } from './api/client'
import MarkdownBody from './components/MarkdownBody.vue'
import ExecutionTimeline from './components/ExecutionTimeline.vue'
import { buildChatBubbles, shortThreadLabel } from './composables/chatBubbles'
import {
  buildLiveOverview,
  mergeOverviews,
} from './composables/liveOverview'
import { useHealth } from './composables/useHealth'
import { useMcp } from './composables/useMcp'
import { useSidebarLayout } from './composables/useSidebarLayout'
import { useSkills } from './composables/useSkills'
import type {
  ArtifactItem,
  AuditItem,
  ChatMessage,
  HitlPreview,
  InterruptInfo,
  RunOverview,
  StageBucket,
  ThreadItem,
  TodoItem,
  Trace,
  TraceStep,
} from './types'

const question = ref('我的 Outlook 一直登录不上')
const loading = ref(false)
const useStream = ref(true)
const {
  health,
  llmConfigured,
  raglabOk,
  raglabLabel,
  sandboxOk,
  sandboxLabel,
  healthChecking,
  checkHealth,
} = useHealth()
const threadId = ref<string | null>(null)
const taskId = ref<string | null>(null)
const status = ref('')
const workspacePath = ref<string | null>(null)
const interrupt = ref<InterruptInfo | null>(null)
const messages = ref<ChatMessage[]>([])
const steps = ref<TraceStep[]>([])
const appliedWrites = ref<unknown[]>([])
const liveEvents = ref<string[]>([])
const threadList = ref<ThreadItem[]>([])
const auditList = ref<AuditItem[]>([])
const todos = ref<TodoItem[]>([])
const artifacts = ref<ArtifactItem[]>([])
const artifactContent = ref<string | null>(null)
const artifactFocus = ref<string | null>(null)
const activeTab = ref('trace')
const viewMode = ref<'chat' | 'workspace'>('chat')
const lastError = ref<string | null>(null)
const lastQuestion = ref('')
const overview = ref<RunOverview | null>(null)
/** Snapshot of thread-cumulative overview at stream start (merged with live steps). */
const overviewBaseline = ref<RunOverview | null>(null)
const overviewLiveActive = ref(false)
const overviewOpen = ref(true)
const stagesPanelOpen = ref(false)
const openStages = ref<Record<string, boolean>>({})
const metrics = ref<Record<string, unknown> | null>(null)
const streamingText = ref('')
const chatScrollEl = ref<HTMLElement | null>(null)

const { layoutStyle, layoutNarrow, resizing, startResize } = useSidebarLayout()

const {
  skillsInstalled,
  skillsCatalog,
  skillsImportedEnabled,
  skillsBusy,
  refreshSkills,
  toggleSkill,
  setImportedLayer,
  importCatalogSkill,
} = useSkills()

const {
  mcpLocalTools,
  mcpRemoteEnabled,
  mcpServers,
  mcpRuntime,
  mcpBusy,
  newMcpName,
  newMcpUrl,
  newMcpTransport,
  newMcpDesc,
  refreshMcp,
  patchMcpSettings,
  toggleMcpServer,
  addMcpServer,
  removeMcpServer,
  reloadMcp,
} = useMcp()

const hasInterrupt = computed(() => Boolean(interrupt.value))
const isAskInterrupt = computed(() => interrupt.value?.type === 'ask')
const isHitlInterrupt = computed(
  () => hasInterrupt.value && interrupt.value?.type !== 'ask',
)
const chatBubbles = computed(() =>
  buildChatBubbles(messages.value, interrupt.value),
)

/** Side-panel overview: live-merge during SSE, authoritative record after done. */
const displayOverview = computed<RunOverview | null>(() => {
  if (overviewLiveActive.value) {
    const live = buildLiveOverview(steps.value, todos.value, status.value || 'running')
    return mergeOverviews(overviewBaseline.value, live)
  }
  return overview.value
})

const composerPlaceholder = computed(() =>
  isAskInterrupt.value
    ? '回复以继续（回答 Agent 的提问）'
    : '输入支持请求，同一会话可多轮续聊…',
)

async function scrollChatToBottom() {
  await nextTick()
  const el = chatScrollEl.value
  if (el) el.scrollTop = el.scrollHeight
}
const submitLabel = computed(() =>
  isAskInterrupt.value ? '发送回复' : '发送 / 继续',
)
const pendingPreview = computed<HitlPreview[]>(() => {
  if (isAskInterrupt.value) return []
  const fromInterrupt = interrupt.value?.pending_preview
  if (fromInterrupt?.length) return fromInterrupt
  const writes = interrupt.value?.pending_writes || []
  return writes
    .filter((w) => w.name)
    .map((w) => ({
      name: w.name as string,
      label: w.name as string,
      highlights: Object.entries((w.args as Record<string, unknown>) || {})
        .filter(([, v]) => v !== null && v !== undefined && v !== '')
        .map(([k, v]) => ({ key: k, value: String(v) })),
      args: (w.args as Record<string, unknown>) || {},
    }))
})

const stageBuckets = computed<StageBucket[]>(() => {
  if (displayOverview.value?.stages?.length) return displayOverview.value.stages
  return []
})

const threadDurationLabel = computed(() => {
  const ms =
    displayOverview.value?.thread_duration_ms ?? displayOverview.value?.duration_ms
  if (ms == null) return overviewLiveActive.value ? '进行中' : '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(1)} s`
})

const threadRunCount = computed(() => displayOverview.value?.run_count ?? 1)

function beginLiveOverview() {
  overviewBaseline.value = overview.value
    ? (JSON.parse(JSON.stringify(overview.value)) as RunOverview)
    : null
  overviewLiveActive.value = true
}

function endLiveOverview() {
  overviewLiveActive.value = false
  overviewBaseline.value = null
}

function applyRecord(data: Record<string, unknown>) {
  threadId.value = (data.thread_id as string) || threadId.value
  taskId.value = (data.task_id as string) || taskId.value
  status.value = (data.status as string) || status.value
  workspacePath.value = (data.workspace_path as string) || workspacePath.value
  interrupt.value = (data.interrupt as InterruptInfo) || null
  appliedWrites.value = (data.applied_writes as unknown[]) || []
  if (Array.isArray(data.messages)) {
    messages.value = data.messages as ChatMessage[]
  }
  if (Array.isArray(data.todos)) {
    todos.value = data.todos as TodoItem[]
  }
  if (Array.isArray(data.artifacts)) {
    artifacts.value = data.artifacts as ArtifactItem[]
  }
  if (data.overview && typeof data.overview === 'object') {
    overview.value = data.overview as RunOverview
  } else if (overviewLiveActive.value) {
    // done 未带 overview 时，把本轮 live 统计落成当前概览
    overview.value = mergeOverviews(
      overviewBaseline.value,
      buildLiveOverview(steps.value, todos.value, status.value),
    )
  }
  if (data.metrics && typeof data.metrics === 'object') {
    metrics.value = data.metrics as Record<string, unknown>
  }
  const trace = data.trace as Trace | undefined
  if (trace?.steps?.length) {
    steps.value = trace.steps
  }
  if (!overview.value && trace?.stages?.length) {
    overview.value = {
      status: status.value,
      stages: trace.stages,
      skills: trace.skills_used || [],
      plan: {
        total: todos.value.length,
        completed: todos.value.filter((t) => t.status === 'completed').length,
        items: todos.value,
      },
    }
  }
  // Authoritative server overview replaces any live merge
  endLiveOverview()
}

async function refreshThreads() {
  try {
    const res = await fetch(`${API}/api/tasks/threads?limit=40`)
    if (!res.ok) return
    const data = await res.json()
    threadList.value = data.items || []
  } catch {
    /* ignore */
  }
}

async function refreshAudit() {
  try {
    const res = await fetch(`${API}/api/tasks/meta/audit?limit=30`)
    if (!res.ok) return
    const data = await res.json()
    auditList.value = data.items || []
  } catch {
    /* ignore */
  }
}

function newThread() {
  threadId.value = null
  taskId.value = null
  status.value = ''
  workspacePath.value = null
  interrupt.value = null
  messages.value = []
  steps.value = []
  appliedWrites.value = []
  liveEvents.value = []
  todos.value = []
  artifacts.value = []
  artifactContent.value = null
  artifactFocus.value = null
  overview.value = null
  endLiveOverview()
  metrics.value = null
  openStages.value = {}
  stagesPanelOpen.value = false
  viewMode.value = 'chat'
  lastError.value = null
  question.value = ''
  ElMessage.info('已新建会话（下一轮提交将创建新 Thread）')
}

async function openThread(item: ThreadItem) {
  try {
    const res = await fetch(`${API}/api/tasks/${item.latest_task_id}`)
    if (!res.ok) throw new Error('task not found')
    const data = await res.json()
    applyRecord(data)
    lastError.value = null
    stagesPanelOpen.value = false
    viewMode.value = 'chat'
    activeTab.value = 'trace'
    await refreshArtifacts()
    ElMessage.success(`已打开会话 · ${item.run_count} 次运行`)
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : String(e)
    ElMessage.error(`加载失败: ${lastError.value}`)
  }
}

async function clearThread(item: ThreadItem, ev?: Event) {
  ev?.stopPropagation()
  const ok = window.confirm(
    `清除会话「${shortThreadLabel(item.thread_id, item.preview)}」？\n将删除该会话的全部运行记录与工作区文件。`,
  )
  if (!ok) return
  try {
    const res = await fetch(`${API}/api/tasks/threads/${encodeURIComponent(item.thread_id)}`, {
      method: 'DELETE',
      headers: apiHeaders(),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || res.statusText)
    }
    if (threadId.value === item.thread_id) {
      newThread()
    }
    await refreshThreads()
    ElMessage.success('会话已清除')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

function stepTagType(kind: string) {
  if (kind === 'subagent_dispatch') return 'danger'
  if (kind === 'context_offload') return 'warning'
  if (kind === 'tool_call') return 'warning'
  if (kind === 'tool_result') return 'success'
  if (kind === 'user') return 'info'
  if (kind === 'assistant') return ''
  return 'info'
}

function todoTagType(status: TodoItem['status']) {
  if (status === 'completed') return 'success'
  if (status === 'in_progress') return 'warning'
  return 'info'
}

async function refreshArtifacts() {
  if (!taskId.value) return
  try {
    const res = await fetch(`${API}/api/tasks/${taskId.value}/artifacts`)
    if (!res.ok) return
    const data = await res.json()
    artifacts.value = data.items || []
  } catch {
    /* ignore */
  }
}

async function openArtifact(item: ArtifactItem) {
  if (!taskId.value) return
  try {
    const res = await fetch(
      `${API}/api/tasks/${taskId.value}/artifacts/${encodeURIComponent(item.path)}`,
    )
    if (!res.ok) throw new Error('artifact not found')
    const data = await res.json()
    artifactFocus.value = item.path
    artifactContent.value = data.content || ''
    // Stay on the conversation page — workspace is opt-in via toolbar
    viewMode.value = 'chat'
    ElMessage.success(`已加载 ${item.name}（可点「工作区」查看全文）`)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : String(e))
  }
}

function formatArgs(args: unknown) {
  try {
    return JSON.stringify(args, null, 2)
  } catch {
    return String(args)
  }
}

async function submitSync(message: string) {
  const res = await fetch(`${API}/api/tasks`, {
    method: 'POST',
    headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      message,
      thread_id: threadId.value,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || res.statusText)
  }
  const data = await res.json()
  applyRecord(data)
}

function handleSseEvent(event: string, data: string) {
  liveEvents.value.push(event)
  let payload: Record<string, unknown>
  try {
    payload = JSON.parse(data)
  } catch {
    // done 偶发超大/截断时：若已收到 interrupt，视为本轮成功暂停
    if (event === 'done' && interrupt.value) {
      status.value = 'interrupted'
      streamingText.value = ''
      return
    }
    if (event === 'done' || event === 'interrupt' || event === 'error') {
      throw new Error(`SSE ${event} 解析失败`)
    }
    return
  }

  if (event === 'token') {
    const text = String(payload.text || '')
    if (text) {
      streamingText.value += text
      void scrollChatToBottom()
    }
    return
  }

  if (
    event === 'tool_start' ||
    event === 'tool_end' ||
    event === 'subagent' ||
    event === 'subagent_progress' ||
    event === 'context_offload'
  ) {
    // New tool activity: commit any in-progress token draft into the bubble stream
    if (streamingText.value.trim()) {
      messages.value = [
        ...messages.value,
        { role: 'assistant', content: streamingText.value },
      ]
      streamingText.value = ''
    }
    const step = payload as unknown as TraceStep
    // Nested subagent LLM hint — show as a light assistant note in the step list
    if (event === 'subagent_progress' && step.kind === 'assistant' && step.content) {
      steps.value = [
        ...steps.value,
        {
          ...step,
          kind: 'assistant',
          content: String(step.content),
        },
      ]
      return
    }
    steps.value = [...steps.value, step]
    // Keep ask_user question in the transcript immediately (survives after interrupt clears)
    if (event === 'tool_start' && step.name === 'ask_user') {
      const args = (step.args || {}) as { question?: string }
      const q = String(args.question || '').trim()
      if (q) {
        const last = messages.value[messages.value.length - 1]
        if (!(last?.role === 'assistant' && last.content === q)) {
          messages.value = [
            ...messages.value,
            {
              role: 'assistant',
              content: q,
              tool_calls: [{ name: 'ask_user', args: { question: q } }],
            },
          ]
        }
      }
    }
    return
  }

  if (event === 'message') {
    const step = payload as unknown as TraceStep
    steps.value = [...steps.value, step]
    if (step.kind === 'assistant' && step.content) {
      streamingText.value = ''
      const content = String(step.content)
      const last = messages.value[messages.value.length - 1]
      const lastText = String(last?.content || '')
      if (last?.role === 'assistant') {
        if (lastText === content) {
          /* noop */
        } else if (content.includes(lastText) && content.length >= lastText.length) {
          messages.value = [...messages.value.slice(0, -1), { ...last, content }]
        } else if (!lastText.includes(content)) {
          messages.value = [
            ...messages.value.slice(0, -1),
            { ...last, content: `${lastText}\n\n${content}` },
          ]
        }
      } else {
        messages.value = [...messages.value, { role: 'assistant', content }]
      }
      void scrollChatToBottom()
    }
    return
  }

  if (event === 'todos' && Array.isArray(payload.todos)) {
    todos.value = payload.todos as TodoItem[]
    return
  }

  if (event === 'interrupt') {
    if (streamingText.value.trim()) {
      messages.value = [
        ...messages.value,
        { role: 'assistant', content: streamingText.value },
      ]
      streamingText.value = ''
    }
    const info = payload as InterruptInfo
    if (info.type === 'ask' && info.question) {
      const q = info.question.trim()
      const last = messages.value[messages.value.length - 1]
      const lastText = String(last?.content || '')
      if (q && !(last?.role === 'assistant' && (lastText === q || lastText.includes(q)))) {
        messages.value = [
          ...messages.value,
          {
            role: 'assistant',
            content: q,
            tool_calls: [{ name: 'ask_user', args: { question: q } }],
          },
        ]
      }
    }
    interrupt.value = info
    status.value = 'interrupted'
    viewMode.value = 'chat'
    void scrollChatToBottom()
    return
  }

  if (event === 'done') {
    streamingText.value = ''
    applyRecord(payload)
    void scrollChatToBottom()
    return
  }

  if (event === 'status' && payload.task_id) {
    taskId.value = payload.task_id as string
    threadId.value = (payload.thread_id as string) || threadId.value
    status.value = (payload.status as string) || status.value
    if (payload.workspace_path) workspacePath.value = payload.workspace_path as string
    return
  }

  if (event === 'error') {
    throw new Error(String(payload.error || 'stream error'))
  }

  // Heartbeat ping — keep connection alive, reset inactivity timer
  if (event === 'ping') {
    // Silently ignore — connection is alive
    return
  }
}

async function consumeSseResponse(res: Response) {
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || res.statusText)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let lastEventTime = Date.now()
  const INACTIVITY_TIMEOUT = 5 * 60 * 1000 // 5 minutes — safety net

  const flushParts = (parts: string[]) => {
    for (const part of parts) {
      if (!part.trim()) continue
      const lines = part.split('\n')
      let event = 'message'
      let data = ''
      for (const line of lines) {
        const raw = line.endsWith('\r') ? line.slice(0, -1) : line
        if (raw.startsWith('event:')) {
          event = raw.slice(6).trim()
          continue
        }
        if (raw.startsWith('data:')) {
          const piece = raw.startsWith('data: ') ? raw.slice(6) : raw.slice(5)
          data = data ? `${data}\n${piece}` : piece
        }
      }
      if (!data) continue
      lastEventTime = Date.now() // Reset timer on any event
      handleSseEvent(event, data)
    }
  }

  const takeFrames = (finalize: boolean) => {
    const normalized = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
    const parts = normalized.split('\n\n')
    if (finalize) {
      buffer = ''
      flushParts(parts)
      return
    }
    buffer = parts.pop() || ''
    flushParts(parts)
  }

  while (true) {
    // Check inactivity timeout
    if (Date.now() - lastEventTime > INACTIVITY_TIMEOUT) {
      throw new Error(
        `SSE 连接超时：${Math.round(INACTIVITY_TIMEOUT / 1000)} 秒内未收到任何事件。` +
        '可能后端卡死或网络连接中断。请刷新页面重试。'
      )
    }

    // Race between reader.read() and timeout check
    const readPromise = reader.read()
    const timeoutPromise = new Promise<{ done: boolean; value: Uint8Array | null }>((_, reject) => {
      setTimeout(() => {
        if (Date.now() - lastEventTime > INACTIVITY_TIMEOUT) {
          reject(new Error(
            `SSE 连接超时：${Math.round(INACTIVITY_TIMEOUT / 1000)} 秒内未收到任何事件。` +
            '可能后端卡死或网络连接中断。请刷新页面重试。'
          ))
        }
      }, 5000) // Check every 5 seconds
    })

    try {
      const { done, value } = await Promise.race([readPromise, timeoutPromise])
      if (value) {
        buffer += decoder.decode(value, { stream: true })
      }
      if (done) {
        buffer += decoder.decode()
        takeFrames(true)
        break
      }
      takeFrames(false)
    } catch (e) {
      // Timeout or other error
      reader.cancel().catch(() => {}) // Cleanup
      throw e
    }
  }
}

async function submitStream(message: string) {
  liveEvents.value = []
  steps.value = []
  streamingText.value = ''
  // Keep conversation history; only clear run-local interrupt until stream updates it
  interrupt.value = null
  status.value = 'running'
  beginLiveOverview()
  const res = await fetch(`${API}/api/tasks/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({
      message,
      thread_id: threadId.value,
    }),
  })
  await consumeSseResponse(res)
}

async function resumeAsk() {
  if (!threadId.value) return
  const answer = question.value.trim()
  if (!answer) {
    ElMessage.warning('请先填写回复')
    return
  }
  loading.value = true
  lastError.value = null
  // Drop pending banner immediately; question stays in transcript as a normal bubble
  interrupt.value = null
  status.value = 'running'
  viewMode.value = 'chat'
  liveEvents.value = []
  steps.value = []
  streamingText.value = ''
  messages.value = [...messages.value, { role: 'user', content: answer }]
  beginLiveOverview()
  const sent = answer
  question.value = ''
  try {
    if (useStream.value) {
      const res = await fetch(`${API}/api/tasks/resume/stream`, {
        method: 'POST',
        headers: apiHeaders({
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        }),
        body: JSON.stringify({
          thread_id: threadId.value,
          task_id: taskId.value,
          interrupt_type: 'ask',
          answer: sent,
        }),
      })
      await consumeSseResponse(res)
    } else {
      const res = await fetch(`${API}/api/tasks/resume`, {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          thread_id: threadId.value,
          task_id: taskId.value,
          interrupt_type: 'ask',
          answer: sent,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || res.statusText)
      }
      applyRecord(await res.json())
    }
    viewMode.value = 'chat'
    ElMessage.success(status.value === 'interrupted' ? '等待你的操作' : '已回复并继续')
    await Promise.all([refreshThreads(), refreshAudit(), refreshArtifacts()])
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : String(e)
    ElMessage.error(`继续失败: ${lastError.value}`)
    endLiveOverview()
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!question.value.trim()) {
    ElMessage.warning(isAskInterrupt.value ? '请填写回复' : '请输入问题')
    return
  }
  if (isAskInterrupt.value) {
    await resumeAsk()
    return
  }
  if (llmConfigured.value === false) {
    ElMessage.warning('未配置 LLM（DEEPSEEK_API_KEY），任务可能失败')
  }
  loading.value = true
  lastError.value = null
  lastQuestion.value = question.value
  appliedWrites.value = []
  const outbound = question.value.trim()
  messages.value = [...messages.value, { role: 'user', content: outbound }]
  question.value = ''
  try {
    if (useStream.value) {
      await submitStream(outbound)
    } else {
      await submitSync(outbound)
    }
    viewMode.value = 'chat'
    ElMessage.success(status.value === 'interrupted' ? '等待你的操作' : '本轮已完成')
    await Promise.all([refreshThreads(), refreshAudit(), refreshArtifacts()])
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : String(e)
    status.value = 'failed'
    // Only restore on failure so an in-flight retry edits don't get clobbered.
    if (!question.value.trim()) question.value = outbound
    ElMessage.error(`执行失败: ${lastError.value}`)
    endLiveOverview()
  } finally {
    loading.value = false
  }
}

async function retryLast() {
  if (lastQuestion.value) {
    question.value = lastQuestion.value
  }
  if (status.value === 'failed') {
    // Keep thread for retry in same conversation; only clear if no thread yet
    if (!threadId.value) {
      taskId.value = null
    }
  }
  await submit()
}

async function resume(approved: boolean) {
  if (!threadId.value || isAskInterrupt.value) return
  loading.value = true
  lastError.value = null
  viewMode.value = 'chat'
  const labels = pendingPreview.value.map((p) => p.label || p.name).filter(Boolean).join('、')
  // Show the decision immediately; the backend also persists it as a SystemMessage in the
  // checkpoint transcript (survives refresh), and the final SSE `done` replaces this local copy.
  messages.value = [
    ...messages.value,
    {
      role: 'system',
      content: approved
        ? `已批准写操作${labels ? `：${labels}` : ''}`
        : `已拒绝写操作${labels ? `：${labels}` : ''}`,
    },
  ]
  try {
    if (useStream.value) {
      liveEvents.value = []
      steps.value = []
      streamingText.value = ''
      interrupt.value = null
      status.value = 'running'
      beginLiveOverview()
      const res = await fetch(`${API}/api/tasks/resume/stream`, {
        method: 'POST',
        headers: apiHeaders({
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        }),
        body: JSON.stringify({
          thread_id: threadId.value,
          task_id: taskId.value,
          interrupt_type: 'hitl',
          approved,
        }),
      })
      await consumeSseResponse(res)
    } else {
      const res = await fetch(`${API}/api/tasks/resume`, {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          thread_id: threadId.value,
          task_id: taskId.value,
          interrupt_type: 'hitl',
          approved,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || res.statusText)
      }
      const data = await res.json()
      applyRecord(data)
      interrupt.value = (data.interrupt as InterruptInfo) || null
    }
    viewMode.value = 'chat'
    ElMessage.success(approved ? '已批准并落库' : '已拒绝')
    await Promise.all([refreshThreads(), refreshAudit(), refreshArtifacts()])
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : String(e)
    ElMessage.error(`恢复失败: ${lastError.value}`)
    endLiveOverview()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await checkHealth()
  await Promise.all([refreshThreads(), refreshAudit(), refreshSkills(), refreshMcp()])
})
</script>

<template>
  <div class="page">
    <header class="header">
      <div class="brand-row">
        <div class="brand-mark" aria-hidden="true">DS</div>
        <div class="brand-text">
          <h1>DeepSupport OS</h1>
          <p class="tagline">企业 IT 支持智能体控制台 · Deep Agents Harness</p>
        </div>
      </div>
      <div class="deps-bar">
        <div class="deps-copy">
          <span class="deps-label">运行依赖</span>
          <span class="deps-hint">后端 / LLM / 知识库 / 沙箱；点右侧可重新探测</span>
        </div>
        <div class="status-rail" role="status" aria-live="polite">
          <span
            class="status-chip"
            :class="health.includes('正常') ? 'is-ok' : health.includes('无法') || health.includes('异常') ? 'is-bad' : 'is-idle'"
            title="DeepSupport API 存活（/health）"
          >
            <i class="dot" />{{ health }}
          </span>
          <span
            v-if="llmConfigured !== null"
            class="status-chip"
            :class="llmConfigured ? 'is-ok' : 'is-bad'"
            title="是否已配置 DEEPSEEK_API_KEY"
          >
            <i class="dot" />{{ llmConfigured ? 'LLM 就绪' : 'LLM 未配置' }}
          </span>
          <span
            class="status-chip"
            :class="raglabOk === true ? 'is-ok' : raglabOk === false ? 'is-warn' : 'is-idle'"
            :title="`${raglabLabel} · 外部知识检索（:8001）`"
          >
            <i class="dot" />{{ raglabLabel }}
          </span>
          <span
            class="status-chip"
            :class="sandboxOk === true ? 'is-ok' : sandboxOk === false ? 'is-warn' : 'is-idle'"
            :title="`${sandboxLabel} · Daytona 沙箱`"
          >
            <i class="dot" />{{ sandboxLabel }}
          </span>
          <span
            v-if="useStream"
            class="status-chip is-stream"
            title="提交任务时使用 SSE 流式进度"
          >
            <i class="dot" />SSE
          </span>
          <button
            type="button"
            class="status-chip is-action"
            :class="{ 'is-checking': healthChecking }"
            :disabled="healthChecking"
            title="重新检查后端、LLM、RAGLab、Sandbox"
            @click="checkHealth"
          >
            <i class="dot" />{{ healthChecking ? '检查中…' : '检查依赖' }}
          </button>
        </div>
        <div class="view-switch">
          <button
            type="button"
            class="view-tab"
            :class="{ active: viewMode === 'chat' }"
            @click="viewMode = 'chat'"
          >
            对话
          </button>
          <button
            type="button"
            class="view-tab"
            :class="{ active: viewMode === 'workspace' }"
            @click="viewMode = 'workspace'"
          >
            工作区
          </button>
          <span v-if="status" class="status-chip is-run"><i class="dot" />{{ status }}</span>
        </div>
      </div>
    </header>

    <el-alert
      v-if="llmConfigured === false"
      class="banner"
      title="未检测到 DeepSeek API Key"
      type="error"
      description="请在仓库根目录配置 .env 中的 DEEPSEEK_API_KEY 后重启后端。"
      show-icon
      :closable="false"
    />

    <el-alert
      v-if="raglabOk === false"
      class="banner"
      title="RAGLab 未就绪（外部知识检索）"
      type="warning"
      description="Knowledge 将回退本地 Markdown。请另启 RAGLab：cd ../RAGLab/backend && uv run --python .venv uvicorn app.main:app --reload --host 0.0.0.0 --port 8001"
      show-icon
      :closable="true"
    />

    <el-alert
      v-if="sandboxOk === false"
      class="banner"
      title="Daytona Sandbox 未就绪"
      type="warning"
      description="本地 Skills/工作区仍可用；/sandbox/ 与 run_sandbox_shell 需要 DAYTONA_API_KEY 且沙箱可连通。可在 .env 配置后点「检查依赖」。"
      show-icon
      :closable="true"
    />

    <main
      class="layout"
      :class="[`mode-${viewMode}`, { 'is-resizing': !!resizing }]"
      :style="viewMode === 'chat' ? layoutStyle : undefined"
    >
      <aside v-show="viewMode === 'chat'" class="side">
        <div class="side-head">
          <h3>会话</h3>
          <div class="side-actions">
            <el-button size="small" type="primary" @click="newThread">新建对话</el-button>
            <el-button size="small" plain @click="refreshThreads">刷新</el-button>
          </div>
        </div>
        <div v-if="!threadList.length" class="empty-hint">暂无会话 · 发送一条消息开始</div>
        <button
          v-for="item in threadList"
          :key="item.thread_id"
          class="task-item"
          :class="{ active: item.thread_id === threadId }"
          type="button"
          @click="openThread(item)"
        >
          <div class="task-meta">
            <el-tag size="small" effect="plain">{{ item.latest_status }}</el-tag>
            <span>{{ item.run_count }} 次运行</span>
            <button
              type="button"
              class="thread-clear"
              title="清除会话"
              @click="clearThread(item, $event)"
            >
              清除
            </button>
          </div>
          <div class="task-preview">{{ shortThreadLabel(item.thread_id, item.preview) }}</div>
          <div class="task-meta muted">{{ item.updated_at?.slice(0, 19) || '' }}</div>
        </button>
      </aside>

      <div
        v-show="viewMode === 'chat' && !layoutNarrow"
        class="col-resizer"
        title="拖拽调整左侧宽度"
        @mousedown="startResize('left', $event)"
      />

      <section v-show="viewMode === 'chat'" class="main">
        <div class="chat-panel">
          <div ref="chatScrollEl" class="chat-scroll">
            <div v-if="!chatBubbles.length && !streamingText" class="empty-hint chat-empty">
              对话将显示在这里。同一会话多轮续聊会保留气泡；Agent 缺上下文时会提问并等待你回复。
            </div>
            <div
              v-for="b in chatBubbles"
              :key="b.id"
              class="bubble"
              :class="[`role-${b.role}`, { 'pending-ask': b.pendingAsk }]"
            >
              <div class="bubble-meta">
                <span>
                  {{ b.role === 'user' ? '你' : b.role === 'system' ? '系统' : 'Agent' }}
                </span>
                <el-tag v-if="b.pendingAsk" type="warning" size="small">需要你回答</el-tag>
                <el-tag v-else-if="b.role === 'system'" type="info" size="small" effect="plain">
                  操作记录
                </el-tag>
              </div>
              <MarkdownBody class="bubble-body" :source="b.content" />
            </div>
            <div v-if="streamingText" class="bubble role-assistant streaming">
              <div class="bubble-meta">
                <span>Agent</span>
                <el-tag size="small" effect="plain">输出中</el-tag>
              </div>
              <MarkdownBody class="bubble-body" :source="streamingText" />
            </div>
          </div>

          <el-alert
            v-if="isAskInterrupt"
            class="panel-alert ask-banner"
            title="未结束 · 请直接回复上方提问（答案会进入对话上下文）"
            type="warning"
            description="回复后提问条会消失，问题与答案保留在对话气泡中。"
            show-icon
            :closable="false"
          />

          <details
            v-if="stageBuckets.length"
            class="stages-panel"
            :open="stagesPanelOpen"
            @toggle="stagesPanelOpen = ($event.target as HTMLDetailsElement).open"
          >
            <summary class="stages-head">
              <strong>{{ isAskInterrupt ? '本轮进度（暂停中）' : '本轮运行阶段' }}</strong>
              <span class="muted">{{ stageBuckets.length }} 段 · 默认折叠，点击展开</span>
            </summary>
            <div class="stages-body">
              <details
                v-for="st in stageBuckets"
                :key="st.id"
                class="stage-fold"
                :open="openStages[st.id]"
                @toggle="openStages[st.id] = ($event.target as HTMLDetailsElement).open"
              >
                <summary>
                  <span class="stage-label">{{ st.label }}</span>
                  <span class="muted">{{ st.summary || `${st.step_count} 步` }}</span>
                  <el-tag size="small" effect="plain">{{ st.tool_count ?? 0 }} tools</el-tag>
                </summary>
                <div class="stage-steps">
                  <div v-for="(s, i) in st.steps" :key="i" class="stage-step">
                    <el-tag :type="stepTagType(s.kind)" size="small">{{ s.kind }}</el-tag>
                    <strong v-if="s.name" class="tool-name">{{ s.name }}</strong>
                    <strong v-else-if="s.skill_used" class="tool-name">skill:{{ s.skill_used }}</strong>
                    <span v-if="s.subagent" class="muted"> · {{ s.subagent }}</span>
                    <el-tag v-if="s.tool_source" size="small" effect="plain">{{ s.tool_source }}</el-tag>
                    <pre v-if="s.args">{{ formatArgs(s.args) }}</pre>
                    <pre v-if="s.content">{{ s.content }}</pre>
                  </div>
                </div>
              </details>
            </div>
          </details>

          <el-alert
            v-if="isHitlInterrupt"
            class="panel-alert"
            title="需要人工审批"
            type="warning"
            description="高风险写操作待确认。请核对下方参数后批准或拒绝；批准后将写入 Mock 数据库。"
            show-icon
            :closable="false"
          />

          <section v-if="isHitlInterrupt && pendingPreview.length" class="hitl-preview">
            <h2>待审批写操作</h2>
            <div v-for="(p, i) in pendingPreview" :key="i" class="hitl-card">
              <div class="step-head">
                <el-tag type="danger" size="small">HITL</el-tag>
                <strong>{{ p.label }}</strong>
                <span class="muted">{{ p.name }}</span>
              </div>
              <ul v-if="p.highlights.length" class="hitl-highlights">
                <li v-for="(h, j) in p.highlights" :key="j">
                  <span class="hitl-key">{{ h.key }}</span>
                  <code>{{ h.value }}</code>
                </li>
              </ul>
              <details>
                <summary>完整参数</summary>
                <pre>{{ formatArgs(p.args) }}</pre>
              </details>
            </div>
          </section>

          <div class="composer">
            <label class="composer-label">{{ isAskInterrupt ? '回复以继续' : '支持请求' }}</label>
            <el-input
              v-model="question"
              type="textarea"
              :rows="3"
              :placeholder="composerPlaceholder"
              @keydown.ctrl.enter="submit"
            />
            <div class="actions">
              <el-checkbox v-model="useStream" title="开启后提交走 SSE 流式进度（顶部状态条也会显示 SSE）">
                流式进度 (SSE)
              </el-checkbox>
              <div class="actions-right">
                <el-button
                  v-if="lastError"
                  type="warning"
                  :loading="loading"
                  @click="retryLast"
                >
                  重试
                </el-button>
                <el-button
                  v-if="isHitlInterrupt"
                  type="success"
                  :loading="loading"
                  @click="resume(true)"
                >
                  批准继续
                </el-button>
                <el-button
                  v-if="isHitlInterrupt"
                  type="danger"
                  :loading="loading"
                  @click="resume(false)"
                >
                  拒绝
                </el-button>
                <el-button type="primary" :loading="loading" @click="submit">
                  {{ submitLabel }}
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <el-alert
          v-if="lastError"
          class="panel-alert"
          title="任务执行失败"
          type="error"
          :description="lastError"
          show-icon
          :closable="true"
          @close="lastError = null"
        />

        <div v-if="taskId" class="run-meta compact">
          <span class="meta-k">Thread</span>
          <code>{{ threadId?.slice(0, 8) }}…</code>
          <span class="meta-k">Run</span>
          <code>{{ taskId?.slice(0, 8) }}…</code>
          <button type="button" class="linkish" @click="viewMode = 'workspace'">打开工作区 →</button>
        </div>
      </section>

      <div
        v-show="viewMode === 'chat' && !layoutNarrow"
        class="col-resizer"
        title="拖拽调整右侧宽度"
        @mousedown="startResize('right', $event)"
      />

      <aside v-show="viewMode === 'chat'" class="overview" :class="{ collapsed: !overviewOpen }">
        <div class="overview-head">
          <h3>运行概览</h3>
          <button type="button" class="status-chip is-action" @click="overviewOpen = !overviewOpen">
            <i class="dot" />{{ overviewOpen ? '收起' : '展开' }}
          </button>
        </div>
        <template v-if="overviewOpen">
          <div v-if="!displayOverview && !taskId" class="empty-hint">提交任务后显示本会话累计统计</div>
          <template v-else>
            <div v-if="isAskInterrupt" class="ov-block">
              <div class="ov-title">当前等待</div>
              <p class="muted">Agent 正在对话中提问，请在中间输入框直接回复。</p>
            </div>
            <div v-if="isHitlInterrupt" class="ov-block">
              <div class="ov-title">当前等待</div>
              <p class="muted">有高风险写操作待审批，请在对话区批准或拒绝。</p>
            </div>
            <div class="ov-block">
              <div class="ov-title">
                Meta · 本会话累计
                <el-tag v-if="overviewLiveActive" size="small" type="warning" effect="plain">
                  实时
                </el-tag>
              </div>
              <p><span class="meta-k">状态</span> {{ displayOverview?.status || status || '—' }}</p>
              <p><span class="meta-k">运行</span> {{ threadRunCount }} 次</p>
              <p><span class="meta-k">会话耗时</span> {{ threadDurationLabel }}</p>
              <p>
                <span class="meta-k">步骤</span>
                {{ displayOverview?.step_count ?? steps.length }}
              </p>
            </div>
            <div class="ov-block">
              <div class="ov-title">
                规划
                <span class="muted">
                  {{ displayOverview?.plan?.completed ?? todos.filter((t) => t.status === 'completed').length }}
                  /
                  {{ displayOverview?.plan?.total ?? todos.length }}
                </span>
              </div>
              <div v-if="!(displayOverview?.plan?.items || todos).length" class="muted">暂无 todos</div>
              <div
                v-for="(p, i) in displayOverview?.plan?.items || todos"
                :key="i"
                class="ov-row"
              >
                <el-tag :type="todoTagType(p.status)" size="small">{{ p.status }}</el-tag>
                <span>{{ p.content }}</span>
              </div>
            </div>
            <div class="ov-block">
              <div class="ov-title">Agent · {{ displayOverview?.agents?.length || 0 }}</div>
              <div v-if="!displayOverview?.agents?.length" class="muted">未委派 SubAgent</div>
              <el-tag
                v-for="a in displayOverview?.agents || []"
                :key="a"
                size="small"
                class="ov-tag"
                type="danger"
              >
                {{ a }}
              </el-tag>
            </div>
            <div class="ov-block">
              <div class="ov-title">Skill · {{ displayOverview?.skills?.length || 0 }}</div>
              <div v-if="!displayOverview?.skills?.length" class="muted">未读 Skill 文件</div>
              <el-tag
                v-for="s in displayOverview?.skills || []"
                :key="s"
                size="small"
                class="ov-tag"
                type="success"
              >
                {{ s }}
              </el-tag>
            </div>
            <div class="ov-block">
              <div class="ov-title">MCP / 来源 · 累计</div>
              <p class="muted">
                本地 {{ displayOverview?.mcp?.local_calls ?? 0 }} ·
                知识 {{ displayOverview?.mcp?.knowledge_calls ?? 0 }} ·
                远程 {{ displayOverview?.mcp?.remote_calls ?? 0 }}
              </p>
              <p v-if="displayOverview?.mcp?.servers?.length" class="muted">
                servers: {{ displayOverview.mcp.servers.join(', ') }}
              </p>
            </div>
            <div class="ov-block">
              <div class="ov-title">
                Tool · {{ displayOverview?.tools?.total_calls ?? 0 }} 次（累计）
              </div>
              <div
                v-for="t in (displayOverview?.tools?.items || []).slice(0, 10)"
                :key="t.name"
                class="ov-row"
              >
                <code class="tool-name">{{ t.name }}</code>
                <span class="muted">×{{ t.count }}</span>
              </div>
            </div>
            <div class="ov-block" v-if="artifacts.length">
              <div class="ov-title">产物 · {{ artifacts.length }}</div>
              <button
                v-for="a in artifacts.slice(0, 6)"
                :key="a.path"
                type="button"
                class="ov-art"
                @click="openArtifact(a)"
              >
                {{ a.name }}
              </button>
            </div>
          </template>
        </template>
      </aside>

      <section v-show="viewMode === 'workspace'" class="workspace-page">
        <div class="workspace-toolbar">
          <el-button size="small" @click="viewMode = 'chat'">← 返回对话</el-button>
          <div v-if="taskId" class="run-meta compact flat">
            <span class="meta-k">Thread</span>
            <code>{{ threadId }}</code>
            <span class="meta-k">Run</span>
            <code>{{ taskId }}</code>
          </div>
        </div>
        <div class="workspace-panel">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="执行计划" name="plan">
            <div v-if="!todos.length" class="empty-hint">提交任务后将显示 Deep Agents 原生 todos（write_todos）</div>
            <div v-for="(p, i) in todos" :key="i" class="plan-row">
              <el-tag :type="todoTagType(p.status)" size="small">{{ p.status }}</el-tag>
              <strong>{{ p.content }}</strong>
            </div>
          </el-tab-pane>

          <el-tab-pane label="产物" name="artifacts">
            <el-button size="small" :disabled="!taskId" @click="refreshArtifacts">刷新产物</el-button>
            <div v-if="!artifacts.length" class="empty-hint">工作区尚无文件；长任务应写出 diagnosis.md / final_resolution.md 等</div>
            <div v-for="a in artifacts" :key="a.path" class="artifact-row" @click="openArtifact(a)">
              <div class="step-head">
                <el-tag v-if="a.canonical" type="success" size="small">标准</el-tag>
                <strong>{{ a.name }}</strong>
                <span class="muted">{{ a.bytes }} B</span>
              </div>
              <pre v-if="a.preview && artifactFocus !== a.path" class="preview">{{ a.preview }}</pre>
            </div>
            <section v-if="artifactContent !== null" class="artifact-body">
              <h3>{{ artifactFocus }}</h3>
              <pre>{{ artifactContent }}</pre>
            </section>
          </el-tab-pane>

          <el-tab-pane label="执行轨迹" name="trace">
            <section v-if="appliedWrites.length" class="applied">
              <h2>已落库写操作</h2>
              <div v-for="(w, i) in appliedWrites" :key="i" class="code-block">
                <pre>{{ formatArgs(w) }}</pre>
              </div>
            </section>
            <section v-if="steps.length" class="trace">
              <div v-for="(s, i) in steps" :key="i" class="step">
                <div class="step-head">
                  <el-tag :type="stepTagType(s.kind)" size="small">{{ s.kind }}</el-tag>
                  <strong v-if="s.name" class="tool-name">{{ s.name }}</strong>
                  <span v-if="s.subagent" class="muted"> · {{ s.subagent }}</span>
                </div>
                <pre v-if="s.args">{{ formatArgs(s.args) }}</pre>
                <pre v-if="s.content">{{ s.content }}</pre>
              </div>
            </section>
            <div v-else class="empty-hint">提交任务后将在此显示结构化轨迹</div>
            <section v-if="liveEvents.length" class="events">
              <h3>SSE 事件</h3>
              <el-tag v-for="(e, i) in liveEvents" :key="i" size="small" class="ev">{{ e }}</el-tag>
            </section>
          </el-tab-pane>

          <el-tab-pane label="执行时间线" name="timeline">
            <ExecutionTimeline v-if="taskId" :taskId="taskId" />
            <div v-else class="empty-hint">执行任务后将在此显示时间线追踪</div>
          </el-tab-pane>

          <el-tab-pane label="Skills" name="skills">
            <div class="mgmt-toolbar">
              <el-button size="small" :loading="skillsBusy" @click="refreshSkills">刷新</el-button>
              <span class="muted">imported 层</span>
              <el-switch
                :model-value="skillsImportedEnabled"
                :disabled="skillsBusy"
                @change="(v: string | number | boolean) => setImportedLayer(Boolean(v))"
              />
            </div>
            <h3>已安装</h3>
            <div v-if="!skillsInstalled.length" class="empty-hint">暂无 Skills</div>
            <div v-for="s in skillsInstalled" :key="s.path" class="mgmt-row">
              <div class="step-head">
                <el-tag :type="s.layer === 'imported' ? 'warning' : 'info'" size="small">{{ s.layer }}</el-tag>
                <el-tag v-if="s.has_references" size="small">L3</el-tag>
                <strong>{{ s.name }}</strong>
                <el-switch
                  :model-value="s.enabled"
                  :disabled="skillsBusy"
                  @change="(v: string | number | boolean) => toggleSkill(s, Boolean(v))"
                />
              </div>
              <p class="muted desc">{{ s.description || s.path }}</p>
            </div>
            <h3>公开 Catalog</h3>
            <div v-for="c in skillsCatalog" :key="c.id" class="mgmt-row">
              <div class="step-head">
                <strong>{{ c.name }}</strong>
                <el-tag v-if="c.optional" size="small">optional</el-tag>
                <el-button
                  size="small"
                  type="primary"
                  :loading="skillsBusy"
                  @click="importCatalogSkill(c)"
                >
                  {{ c.source === 'cli' ? '查看安装说明' : '导入' }}
                </el-button>
              </div>
              <p class="muted desc">{{ c.description }}</p>
              <p v-if="c.license" class="muted desc">License: {{ c.license }}</p>
            </div>
          </el-tab-pane>

          <el-tab-pane label="MCP" name="mcp">
            <div class="mgmt-toolbar">
              <el-button size="small" :loading="mcpBusy" @click="refreshMcp">刷新</el-button>
              <el-button size="small" type="warning" :loading="mcpBusy" @click="reloadMcp">重载远程工具</el-button>
            </div>
            <div class="mgmt-toolbar">
              <span>本地 Mock 工具</span>
              <el-switch
                :model-value="mcpLocalTools"
                :disabled="mcpBusy"
                @change="(v: string | number | boolean) => patchMcpSettings({ mcp_local_tools: Boolean(v) })"
              />
              <span>远程 MCP</span>
              <el-switch
                :model-value="mcpRemoteEnabled"
                :disabled="mcpBusy"
                @change="(v: string | number | boolean) => patchMcpSettings({ mcp_remote_enabled: Boolean(v) })"
              />
            </div>
            <p v-if="mcpRuntime.error" class="muted">运行时: {{ mcpRuntime.error }}</p>
            <p v-else-if="mcpRuntime.tool_count != null" class="muted">
              已加载远程工具 {{ mcpRuntime.tool_count }} 个
              <span v-if="Array.isArray(mcpRuntime.tool_names)">
                · {{ (mcpRuntime.tool_names as string[]).slice(0, 8).join(', ') }}
              </span>
            </p>
            <h3>已配置 Servers</h3>
            <div v-if="!Object.keys(mcpServers).length" class="empty-hint">暂无 MCP server</div>
            <div v-for="(spec, name) in mcpServers" :key="name" class="mgmt-row">
              <div class="step-head">
                <strong>{{ name }}</strong>
                <el-tag size="small">{{ spec.transport }}</el-tag>
                <el-switch
                  :model-value="spec.enabled"
                  :disabled="mcpBusy"
                  @change="(v: string | number | boolean) => toggleMcpServer(String(name), Boolean(v))"
                />
                <el-button size="small" type="danger" text :disabled="mcpBusy" @click="removeMcpServer(String(name))">
                  删除
                </el-button>
              </div>
              <p class="muted desc">{{ spec.description || spec.url || spec.command }}</p>
            </div>
            <h3>添加远程 MCP</h3>
            <div class="mcp-form">
              <el-input v-model="newMcpName" size="small" placeholder="名称 (如 github-mcp)" />
              <el-select v-model="newMcpTransport" size="small" style="width: 160px">
                <el-option label="streamable_http" value="streamable_http" />
                <el-option label="sse" value="sse" />
                <el-option label="http" value="http" />
              </el-select>
              <el-input v-model="newMcpUrl" size="small" placeholder="URL" />
              <el-input v-model="newMcpDesc" size="small" placeholder="说明（可选）" />
              <el-button size="small" type="primary" :loading="mcpBusy" @click="addMcpServer">添加</el-button>
            </div>
          </el-tab-pane>

          <el-tab-pane label="审计日志" name="audit">
            <el-button size="small" @click="refreshAudit">刷新审计</el-button>
            <div v-if="!auditList.length" class="empty-hint">暂无审计记录</div>
            <div v-for="a in auditList" :key="a.id" class="audit-row">
              <div class="step-head">
                <el-tag size="small">{{ a.tool }}</el-tag>
                <span class="muted">{{ a.timestamp }} · {{ a.task_id }}</span>
              </div>
              <pre>{{ a.result }}</pre>
            </div>
          </el-tab-pane>

          <el-tab-pane label="执行时间线" name="timeline">
            <ExecutionTimeline v-if="taskId" :task-id="taskId" />
            <div v-else class="empty-hint">请先提交任务以查看执行时间线</div>
          </el-tab-pane>
        </el-tabs>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.page {
  max-width: none;
  width: 100%;
  margin: 0;
  padding: 12px 8px 20px;
  animation: page-in 0.45s ease-out;
}

@keyframes page-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 4px 6px;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.02em;
  color: #ffffff;
  background: linear-gradient(135deg, #27272a 0%, #18181b 100%);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.brand-text h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--text-title);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--fg-primary);
}

.tagline {
  margin: 4px 0 0;
  color: var(--fg-secondary);
  font-size: var(--text-sm);
}

.deps-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
}

.deps-copy {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 12px;
}

.deps-label {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--fg-secondary);
}

.deps-label.soft {
  color: var(--fg-muted);
}

.deps-hint {
  font-size: var(--text-sm);
  color: var(--fg-muted);
}

.status-rail {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.run-status-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding-top: 4px;
  border-top: 1px solid var(--border);
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: var(--text-xs);
  font-weight: 500;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--fg-secondary);
  transition: border-color 0.15s, transform 0.15s;
}

.status-chip:hover {
  border-color: var(--border-strong);
}

.status-chip .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.5;
}

.status-chip.is-ok {
  color: var(--success);
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.status-chip.is-ok .dot {
  opacity: 1;
}

.status-chip.is-warn {
  color: var(--warning);
  border-color: #fde68a;
  background: #fffbeb;
}

.status-chip.is-bad {
  color: var(--danger);
  border-color: #fecaca;
  background: #fef2f2;
}

.status-chip.is-run {
  color: var(--accent);
  border-color: #bfdbfe;
  background: #eff6ff;
}

.status-chip.is-run .dot {
  animation: dot-pulse 1.6s ease-in-out infinite;
}

.status-chip.is-stream {
  color: var(--info);
  border-color: #a5f3fc;
  background: #ecfeff;
}

button.status-chip {
  font: inherit;
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
  appearance: none;
}

button.status-chip:disabled {
  cursor: wait;
  opacity: 0.6;
}

.status-chip.is-action {
  color: var(--accent);
  border-color: var(--accent);
  border-style: dashed;
  background: var(--bg-card);
}

.status-chip.is-action:hover:not(:disabled) {
  border-style: solid;
  background: var(--accent-soft);
}

.status-chip.is-action.is-checking .dot {
  animation: dot-pulse 0.9s ease-in-out infinite;
}

.status-chip.is-idle .dot {
  animation: dot-pulse 1.6s ease-in-out infinite;
}

.banner,
.panel-alert {
  margin-top: 14px;
  border-radius: var(--radius-sm);
}

.view-switch {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}

.view-tab {
  appearance: none;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--fg-secondary);
  border-radius: var(--radius-sm);
  padding: 6px 14px;
  font-size: var(--text-base);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.view-tab:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.view-tab.active {
  color: #fff;
  background: var(--primary);
  border-color: var(--primary);
}

.layout {
  display: grid;
  grid-template-columns: 228px 6px minmax(0, 1fr) 6px 280px;
  gap: 0 8px;
  margin-top: 12px;
  align-items: stretch;
  min-height: calc(100vh - 160px);
}

.layout.mode-workspace {
  grid-template-columns: 1fr;
  min-height: calc(100vh - 168px);
  gap: 10px;
}

.col-resizer {
  width: 6px;
  margin: 0 -1px;
  cursor: col-resize;
  border-radius: 4px;
  background: transparent;
  position: relative;
  z-index: 2;
  align-self: stretch;
  touch-action: none;
}

.col-resizer::after {
  content: '';
  position: absolute;
  top: 12%;
  bottom: 12%;
  left: 50%;
  width: 3px;
  transform: translateX(-50%);
  border-radius: 2px;
  background: var(--border-strong);
  opacity: 0.5;
  transition: opacity 0.15s, background 0.15s;
}

.col-resizer:hover::after,
.layout.is-resizing .col-resizer::after {
  opacity: 1;
  background: var(--accent);
}

@media (max-width: 1280px) {
  .layout.mode-chat {
    grid-template-columns: 220px minmax(0, 1fr);
    gap: 10px;
  }
  .layout.mode-chat .overview {
    grid-column: 1 / -1;
    position: static;
    max-height: none;
  }
}

@media (max-width: 900px) {
  .layout.mode-chat {
    grid-template-columns: 1fr;
  }
}

.side,
.composer,
.workspace-panel,
.hitl-preview,
.overview {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.side {
  padding: 12px;
  position: sticky;
  top: 8px;
  max-height: calc(100vh - 16px);
  overflow: auto;
  background: var(--bg-sidebar);
}

.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.side-head h3,
.workspace-panel h3,
.mgmt-row + h3,
.hitl-preview h2,
.applied h2,
.events h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--fg-primary);
}

.side-actions {
  display: flex;
  gap: 6px;
}

.task-item {
  width: 100%;
  text-align: left;
  border: 1px solid var(--border);
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.task-item:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-sm);
}

.task-item.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  box-shadow: 0 0 0 1px var(--accent);
}

.task-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: var(--text-xs);
  color: var(--fg-muted);
  margin-bottom: 4px;
}

.thread-clear {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--danger);
  cursor: pointer;
  font-size: var(--text-xs);
  padding: 0 2px;
  opacity: 0.7;
}

.thread-clear:hover {
  opacity: 1;
  text-decoration: underline;
}

.task-preview {
  font-size: var(--text-base);
  color: var(--fg-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.main {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  min-height: 0;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 16px 18px;
  flex: 1;
  min-height: calc(100vh - 220px);
}

.chat-scroll {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  min-height: 280px;
  max-height: none;
  overflow: auto;
  padding-right: 4px;
}

.chat-empty {
  margin: 0;
}

.bubble {
  max-width: min(96%, 860px);
  padding: 12px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-sidebar);
}

.bubble.role-user {
  align-self: flex-end;
  background: var(--accent-soft);
  border-color: var(--accent);
}

.bubble.role-assistant {
  align-self: flex-start;
  background: var(--bg-card);
}

.bubble.role-system {
  align-self: center;
  max-width: min(92%, 720px);
  background: var(--bg-sidebar);
  border-style: dashed;
  color: var(--fg-secondary);
  font-size: var(--text-sm);
}

.bubble.streaming .bubble-body::after {
  content: '▋';
  margin-left: 2px;
  opacity: 0.55;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.bubble.pending-ask {
  border-color: var(--warning);
  background: linear-gradient(180deg, #fffbeb 0%, var(--bg-card) 75%);
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.1);
}

.ask-banner {
  border: 1px solid var(--warning) !important;
}

.ask-banner :deep(.el-alert__description) {
  white-space: pre-wrap;
  max-height: 180px;
  overflow: auto;
}

.bubble-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: var(--fg-muted);
}

.bubble-body {
  word-break: break-word;
  font-size: var(--text-base);
  line-height: 1.6;
  color: var(--fg-primary);
}

/* Plain text fallback if MarkdownBody is not used */
.bubble-body:not(.md-body) {
  white-space: pre-wrap;
}

.composer {
  padding: 14px 0 0;
  border-top: 1px solid var(--border);
  background: transparent;
  border-radius: 0;
  box-shadow: none;
  border-left: none;
  border-right: none;
  border-bottom: none;
}

.composer-label {
  display: block;
  margin-bottom: 8px;
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--fg-muted);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}

.actions-right {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.run-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: center;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-sidebar);
  font-size: var(--text-sm);
}

.meta-k {
  color: var(--fg-muted);
  font-weight: 600;
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.run-meta code {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--accent);
  background: var(--accent-soft);
  padding: 2px 6px;
  border-radius: 4px;
}

.run-meta code.ws {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.workspace-panel {
  padding: 8px 16px 16px;
}

.hitl-preview {
  padding: 14px 16px;
  border-color: var(--warning);
  background: linear-gradient(180deg, #fffbeb 0%, var(--bg-card) 70%);
}

.hitl-card + .hitl-card {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.hitl-highlights {
  list-style: none;
  padding: 0;
  margin: 8px 0;
}

.hitl-highlights li {
  display: flex;
  gap: 10px;
  align-items: baseline;
  margin: 4px 0;
  font-size: var(--text-base);
}

.hitl-key {
  min-width: 72px;
  color: var(--warning);
  font-weight: 600;
}

.hitl-highlights code,
.tool-name {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}

.plan-row {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.artifact-row,
.code-block {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  margin: 8px 0;
  background: var(--bg-sidebar);
}

.artifact-row {
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.artifact-row:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-sm);
}

.artifact-row .preview {
  max-height: 80px;
  overflow: hidden;
  opacity: 0.75;
}

.artifact-body {
  margin-top: 12px;
  border-top: 1px solid var(--border);
  padding-top: 12px;
}

.mgmt-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}

.mgmt-row {
  border-bottom: 1px solid var(--border);
  padding: 12px 0;
}

.mgmt-row .desc {
  margin: 6px 0 0;
  font-size: var(--text-sm);
}

.mcp-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
}

.mcp-form .el-input {
  width: min(280px, 100%);
}

.step,
.audit-row {
  border-top: 1px solid var(--border);
  padding: 12px 0;
}

.step-head {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

pre {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 8px 0 0;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--fg-secondary);
}

.events {
  margin-top: 12px;
}

.ev {
  margin: 0 6px 6px 0;
}

.muted {
  color: var(--fg-muted);
  font-size: var(--text-sm);
}

.empty-hint {
  color: var(--fg-muted);
  font-size: var(--text-sm);
  padding: 20px 16px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  text-align: center;
  background: var(--bg-sidebar);
  margin: 8px 0;
}

.stages-panel {
  margin-top: 4px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-sidebar);
  padding: 0 12px;
}

.stages-panel > .stages-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  list-style: none;
  padding: 10px 0;
  font-size: var(--text-base);
  margin: 0;
}

.stages-panel > .stages-head::-webkit-details-marker {
  display: none;
}

.stages-panel > .stages-head::before {
  content: '▸';
  color: var(--fg-muted);
  font-size: var(--text-xs);
}

.stages-panel[open] > .stages-head::before {
  content: '▾';
}

.stages-body {
  padding-bottom: 8px;
}

.linkish {
  appearance: none;
  border: none;
  background: none;
  color: var(--accent);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  padding: 0;
}

.linkish:hover {
  text-decoration: underline;
}

.run-meta.compact {
  padding: 8px 10px;
  font-size: var(--text-xs);
}

.run-meta.compact.flat {
  border: none;
  background: transparent;
  box-shadow: none;
  padding: 0;
}

.workspace-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.workspace-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.stage-fold {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  margin-bottom: 8px;
  padding: 0 12px;
}

.stage-fold summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  list-style: none;
  padding: 10px 0;
  font-size: var(--text-base);
}

.stage-fold summary::-webkit-details-marker {
  display: none;
}

.stage-label {
  font-weight: 600;
  color: var(--fg-primary);
}

.stage-steps {
  border-top: 1px solid var(--border);
  padding: 8px 0 12px;
}

.stage-step {
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.overview {
  padding: 12px;
  position: sticky;
  top: 8px;
  max-height: calc(100vh - 16px);
  overflow: auto;
}

.overview.collapsed {
  max-height: none;
}

.overview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.overview-head h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
}

.ov-block {
  border-top: 1px solid var(--border);
  padding: 10px 0;
}

.ov-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  font-weight: 600;
  font-size: var(--text-sm);
  margin-bottom: 6px;
  color: var(--fg-secondary);
}

.ov-subtitle {
  font-size: var(--text-xs);
  color: var(--fg-muted);
  margin: 8px 0 4px;
}

.ix-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  margin: 6px 0;
  background: var(--bg-sidebar);
  font-size: var(--text-sm);
}

.ix-card.is-ask {
  border-color: var(--warning);
  background: #fffbeb;
}

.ix-card.is-hitl {
  border-color: var(--danger);
  background: #fef2f2;
}

.ix-card p {
  margin: 6px 0 0;
  white-space: pre-wrap;
}

.ix-list {
  margin: 6px 0 0;
  padding-left: 1.1rem;
}

.ix-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.ix-log {
  margin-top: 8px;
}

.ix-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin: 6px 0;
  font-size: var(--text-sm);
}

.ix-body {
  min-width: 0;
}

.ix-body p {
  margin: 2px 0;
  word-break: break-word;
}

.ov-row {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: var(--text-sm);
  margin: 4px 0;
}

.ov-tag {
  margin: 0 4px 4px 0;
}

.ov-art {
  display: block;
  width: 100%;
  text-align: left;
  border: 1px solid var(--border);
  background: var(--bg-sidebar);
  border-radius: var(--radius-sm);
  padding: 6px 8px;
  margin: 4px 0;
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--accent);
}

.ov-art:hover {
  background: var(--accent-soft);
  border-color: var(--accent);
}
</style>
