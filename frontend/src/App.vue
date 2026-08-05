<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { API, apiHeaders } from './api/client'
import { buildChatBubbles, shortThreadLabel } from './composables/chatBubbles'
import { useHealth } from './composables/useHealth'
import { useMcp } from './composables/useMcp'
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

type InteractionItem = {
  id: string
  kind: 'ask' | 'answer' | 'hitl' | 'decision'
  title: string
  detail?: string
  at: string
}

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
const overviewOpen = ref(true)
const stagesPanelOpen = ref(false)
const openStages = ref<Record<string, boolean>>({})
const metrics = ref<Record<string, unknown> | null>(null)
const streamingText = ref('')
const chatScrollEl = ref<HTMLElement | null>(null)
const interactionLog = ref<InteractionItem[]>([])
let interactionSeq = 0

function pushInteraction(
  kind: InteractionItem['kind'],
  title: string,
  detail?: string,
) {
  interactionSeq += 1
  interactionLog.value = [
    {
      id: `ix-${interactionSeq}`,
      kind,
      title,
      detail,
      at: new Date().toLocaleTimeString(),
    },
    ...interactionLog.value,
  ].slice(0, 40)
}

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
const chatBubbles = computed(() => buildChatBubbles(messages.value, interrupt.value))
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
  if (overview.value?.stages?.length) return overview.value.stages
  return []
})

const durationLabel = computed(() => {
  const ms = overview.value?.duration_ms ?? (metrics.value?.duration_ms as number | undefined)
  if (ms == null) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(1)} s`
})

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
  metrics.value = null
  openStages.value = {}
  stagesPanelOpen.value = false
  interactionLog.value = []
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
    ElMessage.success(`已打开会话 · ${item.run_count} 轮`)
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : String(e)
    ElMessage.error(`加载失败: ${lastError.value}`)
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

async function submitSync() {
  const res = await fetch(`${API}/api/tasks`, {
    method: 'POST',
    headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      message: question.value,
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
      pushInteraction('ask', 'Agent 提问', q.slice(0, 160))
    } else if (info.type === 'hitl' || (info.type !== 'ask' && info.pending_preview?.length)) {
      const labels = (info.pending_preview || [])
        .map((p) => p.label || p.name)
        .filter(Boolean)
        .join('、')
      pushInteraction('hitl', '待人工审批', labels || '高风险写操作')
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
}

async function consumeSseResponse(res: Response) {
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || res.statusText)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

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
    const { done, value } = await reader.read()
    if (value) {
      buffer += decoder.decode(value, { stream: true })
    }
    if (done) {
      buffer += decoder.decode()
      takeFrames(true)
      break
    }
    takeFrames(false)
  }
}

async function submitStream() {
  liveEvents.value = []
  steps.value = []
  streamingText.value = ''
  // Keep conversation history; only clear run-local interrupt until stream updates it
  interrupt.value = null
  const res = await fetch(`${API}/api/tasks/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({
      message: question.value,
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
  pushInteraction('answer', '你的回复', answer.slice(0, 160))
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
  messages.value = [...messages.value, { role: 'user', content: question.value.trim() }]
  const outbound = question.value
  question.value = ''
  try {
    // Restore outbound into request body helpers via lastQuestion
    question.value = outbound
    if (useStream.value) {
      await submitStream()
    } else {
      await submitSync()
    }
    question.value = ''
    viewMode.value = 'chat'
    ElMessage.success(status.value === 'interrupted' ? '等待你的操作' : '本轮已完成')
    await Promise.all([refreshThreads(), refreshAudit(), refreshArtifacts()])
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : String(e)
    status.value = 'failed'
    question.value = outbound
    ElMessage.error(`执行失败: ${lastError.value}`)
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
  pushInteraction('decision', approved ? '已批准写操作' : '已拒绝写操作')
  try {
    if (useStream.value) {
      liveEvents.value = []
      steps.value = []
      streamingText.value = ''
      interrupt.value = null
      status.value = 'running'
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

    <main class="layout" :class="[`mode-${viewMode}`]">
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
          </div>
          <div class="task-preview">{{ shortThreadLabel(item.thread_id, item.preview) }}</div>
          <div class="task-meta muted">{{ item.updated_at?.slice(0, 19) || '' }}</div>
        </button>
      </aside>

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
                <span>{{ b.role === 'user' ? '你' : 'Agent' }}</span>
                <el-tag v-if="b.pendingAsk" type="warning" size="small">需要你回答</el-tag>
              </div>
              <div class="bubble-body">{{ b.content }}</div>
            </div>
            <div v-if="streamingText" class="bubble role-assistant streaming">
              <div class="bubble-meta">
                <span>Agent</span>
                <el-tag size="small" effect="plain">输出中</el-tag>
              </div>
              <div class="bubble-body">{{ streamingText }}</div>
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
                    <strong v-if="s.subagent" class="tool-name">{{ s.subagent }}</strong>
                    <strong v-else-if="s.skill_used" class="tool-name">skill:{{ s.skill_used }}</strong>
                    <strong v-else-if="s.name" class="tool-name">{{ s.name }}</strong>
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

      <aside v-show="viewMode === 'chat'" class="overview" :class="{ collapsed: !overviewOpen }">
        <div class="overview-head">
          <h3>运行概览</h3>
          <button type="button" class="status-chip is-action" @click="overviewOpen = !overviewOpen">
            <i class="dot" />{{ overviewOpen ? '收起' : '展开' }}
          </button>
        </div>
        <template v-if="overviewOpen">
          <div v-if="!overview && !taskId && !interactionLog.length" class="empty-hint">提交任务后显示本轮统计</div>
          <template v-else>
            <div
              v-if="isAskInterrupt || isHitlInterrupt || interactionLog.length"
              class="ov-block ov-action"
            >
              <div class="ov-title">待你处理 / 互动</div>
              <div v-if="isAskInterrupt" class="ix-card is-ask">
                <el-tag type="warning" size="small">提问中</el-tag>
                <p>{{ interrupt?.question || '请在下方回复' }}</p>
              </div>
              <div v-if="isHitlInterrupt" class="ix-card is-hitl">
                <el-tag type="danger" size="small">待审批</el-tag>
                <ul v-if="pendingPreview.length" class="ix-list">
                  <li v-for="(p, i) in pendingPreview" :key="i">
                    <strong>{{ p.label || p.name }}</strong>
                    <span v-for="(h, j) in p.highlights.slice(0, 3)" :key="j" class="muted">
                      {{ h.key }}={{ h.value }}
                    </span>
                  </li>
                </ul>
                <div class="ix-actions">
                  <el-button type="success" size="small" :loading="loading" @click="resume(true)">
                    批准
                  </el-button>
                  <el-button type="danger" size="small" plain :loading="loading" @click="resume(false)">
                    拒绝
                  </el-button>
                </div>
              </div>
              <div v-if="interactionLog.length" class="ix-log">
                <div class="ov-subtitle">本会话记录</div>
                <div v-for="ix in interactionLog" :key="ix.id" class="ix-row">
                  <el-tag
                    size="small"
                    :type="
                      ix.kind === 'ask' || ix.kind === 'hitl'
                        ? 'warning'
                        : ix.kind === 'decision'
                          ? 'success'
                          : 'info'
                    "
                  >
                    {{ ix.kind }}
                  </el-tag>
                  <div class="ix-body">
                    <strong>{{ ix.title }}</strong>
                    <p v-if="ix.detail" class="muted">{{ ix.detail }}</p>
                    <span class="muted">{{ ix.at }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="ov-block">
              <div class="ov-title">Meta</div>
              <p><span class="meta-k">状态</span> {{ overview?.status || status || '—' }}</p>
              <p><span class="meta-k">耗时</span> {{ durationLabel }}</p>
              <p><span class="meta-k">步骤</span> {{ overview?.step_count ?? steps.length }}</p>
            </div>
            <div class="ov-block">
              <div class="ov-title">
                规划
                <span class="muted">
                  {{ overview?.plan?.completed ?? todos.filter((t) => t.status === 'completed').length }}
                  /
                  {{ overview?.plan?.total ?? todos.length }}
                </span>
              </div>
              <div v-if="!(overview?.plan?.items || todos).length" class="muted">暂无 todos</div>
              <div
                v-for="(p, i) in overview?.plan?.items || todos"
                :key="i"
                class="ov-row"
              >
                <el-tag :type="todoTagType(p.status)" size="small">{{ p.status }}</el-tag>
                <span>{{ p.content }}</span>
              </div>
            </div>
            <div class="ov-block">
              <div class="ov-title">Agent · {{ overview?.agents?.length || 0 }}</div>
              <div v-if="!overview?.agents?.length" class="muted">未委派 SubAgent</div>
              <el-tag
                v-for="a in overview?.agents || []"
                :key="a"
                size="small"
                class="ov-tag"
                type="danger"
              >
                {{ a }}
              </el-tag>
            </div>
            <div class="ov-block">
              <div class="ov-title">Skill · {{ overview?.skills?.length || 0 }}</div>
              <div v-if="!overview?.skills?.length" class="muted">未读 Skill 文件</div>
              <el-tag
                v-for="s in overview?.skills || []"
                :key="s"
                size="small"
                class="ov-tag"
                type="success"
              >
                {{ s }}
              </el-tag>
            </div>
            <div class="ov-block">
              <div class="ov-title">MCP / 来源</div>
              <p class="muted">
                本地 {{ overview?.mcp?.local_calls ?? 0 }} ·
                知识 {{ overview?.mcp?.knowledge_calls ?? 0 }} ·
                远程 {{ overview?.mcp?.remote_calls ?? 0 }}
              </p>
              <p v-if="overview?.mcp?.servers?.length" class="muted">
                servers: {{ overview.mcp.servers.join(', ') }}
              </p>
            </div>
            <div class="ov-block">
              <div class="ov-title">
                Tool · {{ overview?.tools?.total_calls ?? 0 }} 次
              </div>
              <div
                v-for="t in (overview?.tools?.items || []).slice(0, 10)"
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
                  <strong v-if="s.subagent" class="tool-name">{{ s.subagent }}</strong>
                  <strong v-else-if="s.name" class="tool-name">{{ s.name }}</strong>
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
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 0.95rem;
  letter-spacing: 0.04em;
  color: #ecfdf8;
  background:
    linear-gradient(145deg, #14b8a6 0%, #0f766e 55%, #115e59 100%);
  box-shadow: 0 8px 20px rgba(15, 118, 110, 0.28);
  animation: mark-glow 3.2s ease-in-out infinite;
}

@keyframes mark-glow {
  0%,
  100% {
    box-shadow: 0 8px 20px rgba(15, 118, 110, 0.28);
  }
  50% {
    box-shadow: 0 10px 28px rgba(20, 184, 166, 0.42);
  }
}

.brand-text h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(1.55rem, 2.4vw, 1.9rem);
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--ds-ink);
}

.tagline {
  margin: 4px 0 0;
  color: var(--ds-muted);
  font-size: 0.92rem;
}

.deps-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  border-radius: var(--ds-radius);
  border: 1px solid var(--ds-line);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(8px);
  box-shadow: var(--ds-shadow);
}

.deps-copy {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 12px;
}

.deps-label {
  font-family: var(--font-display);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ds-accent-deep);
}

.deps-label.soft {
  color: var(--ds-muted);
}

.deps-hint {
  font-size: 0.8rem;
  color: var(--ds-muted);
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
  border-top: 1px dashed var(--ds-line);
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 500;
  border: 1px solid var(--ds-line);
  background: rgba(255, 255, 255, 0.72);
  color: var(--ds-ink-soft);
  backdrop-filter: blur(6px);
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.status-chip:hover {
  transform: translateY(-1px);
}

.status-chip .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.55;
}

.status-chip.is-ok {
  color: var(--ds-ok);
  border-color: #a7f3d0;
  background: #ecfdf5;
}

.status-chip.is-ok .dot {
  opacity: 1;
  box-shadow: 0 0 0 3px rgba(4, 120, 87, 0.15);
}

.status-chip.is-warn {
  color: var(--ds-warn);
  border-color: #fde68a;
  background: #fffbeb;
}

.status-chip.is-bad {
  color: var(--ds-danger);
  border-color: #fecaca;
  background: #fef2f2;
}

.status-chip.is-run {
  color: var(--ds-accent-deep);
  border-color: #99f6e4;
  background: #f0fdfa;
}

.status-chip.is-stream {
  color: #0e7490;
  border-color: #a5f3fc;
  background: #ecfeff;
}

button.status-chip {
  font: inherit;
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  appearance: none;
}

button.status-chip:disabled {
  cursor: wait;
  opacity: 0.85;
}

.status-chip.is-action {
  color: var(--ds-accent-deep);
  border-color: #99f6e4;
  background: #f0fdfa;
  border-style: dashed;
}

.status-chip.is-action:hover:not(:disabled) {
  border-style: solid;
  background: #ccfbf1;
}

.status-chip.is-action.is-checking .dot {
  opacity: 1;
  animation: pulse-dot 0.9s ease-in-out infinite;
}

.status-chip.is-idle .dot {
  animation: pulse-dot 1.6s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 0.9;
  }
}

.banner,
.panel-alert {
  margin-top: 14px;
  border-radius: 12px;
}

.view-switch {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding-top: 4px;
  border-top: 1px dashed var(--ds-line);
}

.view-tab {
  appearance: none;
  border: 1px solid var(--ds-line);
  background: rgba(255, 255, 255, 0.7);
  color: var(--ds-ink-soft);
  border-radius: 999px;
  padding: 5px 14px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.view-tab:hover {
  border-color: #99f6e4;
}

.view-tab.active {
  color: #fff;
  background: var(--ds-accent);
  border-color: var(--ds-accent);
}

.layout {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr) 220px;
  gap: 10px;
  margin-top: 10px;
  align-items: stretch;
  min-height: calc(100vh - 168px);
}

.layout.mode-workspace {
  grid-template-columns: 1fr;
  min-height: calc(100vh - 168px);
}

@media (max-width: 1280px) {
  .layout.mode-chat {
    grid-template-columns: 180px minmax(0, 1fr);
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
  background: var(--ds-panel);
  border: 1px solid var(--ds-line);
  border-radius: var(--ds-radius);
  box-shadow: var(--ds-shadow);
}

.side {
  padding: 12px;
  position: sticky;
  top: 8px;
  max-height: calc(100vh - 16px);
  overflow: auto;
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
  font-size: 0.95rem;
  letter-spacing: -0.02em;
}

.side-actions {
  display: flex;
  gap: 6px;
}

.task-item {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  background: var(--ds-surface-solid);
  border-radius: 10px;
  padding: 10px 11px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color 0.18s ease, background 0.18s ease, transform 0.18s ease;
}

.task-item:hover {
  border-color: #99f6e4;
  transform: translateX(2px);
}

.task-item.active {
  border-color: var(--ds-accent);
  background: #f0fdfa;
}

.task-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 0.72rem;
  color: var(--ds-muted);
  margin-bottom: 6px;
}

.task-preview {
  font-size: 0.86rem;
  color: var(--ds-ink-soft);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  background: var(--ds-panel);
  border: 1px solid var(--ds-line);
  border-radius: var(--ds-radius);
  box-shadow: var(--ds-shadow);
  padding: 14px 16px;
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
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--ds-line);
  background: var(--ds-surface-solid);
  animation: page-in 0.28s ease-out;
}

.bubble.role-user {
  align-self: flex-end;
  background: #ecfdf5;
  border-color: #99f6e4;
}

.bubble.role-assistant {
  align-self: flex-start;
  background: #fff;
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
  border-color: #fbbf24;
  background: linear-gradient(180deg, #fffbeb 0%, #fff 75%);
  box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.12);
}

.ask-banner {
  border: 1px solid #fbbf24 !important;
}

.ask-banner :deep(.el-alert__description) {
  white-space: pre-wrap;
  max-height: 180px;
  overflow: auto;
}

.bubble-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ds-muted);
}

.bubble-body {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.95rem;
  line-height: 1.5;
  color: var(--ds-ink);
}

.composer {
  padding: 12px 0 0;
  border-top: 1px dashed var(--ds-line);
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
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ds-muted);
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
  border-radius: 12px;
  border: 1px dashed var(--ds-line-strong);
  background: rgba(255, 255, 255, 0.55);
  font-size: 0.82rem;
}

.meta-k {
  color: var(--ds-muted);
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.run-meta code {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--ds-accent-deep);
  background: #ecfdf5;
  padding: 2px 6px;
  border-radius: 6px;
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
  border-color: #fcd34d;
  background: linear-gradient(180deg, #fffbeb 0%, #fff 70%);
}

.hitl-card + .hitl-card {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #fcd34d;
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
  font-size: 0.9rem;
}

.hitl-key {
  min-width: 72px;
  color: #92400e;
  font-weight: 600;
}

.hitl-highlights code,
.tool-name {
  font-family: var(--font-mono);
  font-size: 0.86rem;
}

.plan-row {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #eef3f1;
}

.artifact-row,
.code-block {
  border: 1px solid var(--ds-line);
  border-radius: 10px;
  padding: 10px 12px;
  margin: 8px 0;
  background: var(--ds-surface-solid);
}

.artifact-row {
  cursor: pointer;
  transition: border-color 0.18s ease, transform 0.18s ease;
}

.artifact-row:hover {
  border-color: #5eead4;
  transform: translateY(-1px);
}

.artifact-row .preview {
  max-height: 80px;
  overflow: hidden;
  opacity: 0.75;
}

.artifact-body {
  margin-top: 12px;
  border-top: 1px solid var(--ds-line);
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
  border-bottom: 1px solid #eef3f1;
  padding: 12px 0;
}

.mgmt-row .desc {
  margin: 6px 0 0;
  font-size: 0.85rem;
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
  border-top: 1px solid #eef3f1;
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
  font-size: 0.82rem;
  color: var(--ds-ink-soft);
}

.events {
  margin-top: 12px;
}

.ev {
  margin: 0 6px 6px 0;
}

.muted {
  color: var(--ds-muted);
  font-size: 0.85rem;
}

.empty-hint {
  color: var(--ds-muted);
  font-size: 0.88rem;
  padding: 18px 4px;
  border: 1px dashed var(--ds-line);
  border-radius: 10px;
  text-align: center;
  background: rgba(244, 248, 246, 0.7);
  margin: 8px 0;
}

.stages-panel {
  margin-top: 4px;
  border: 1px dashed var(--ds-line);
  border-radius: 12px;
  background: rgba(244, 248, 246, 0.65);
  padding: 0 10px;
}

.stages-panel > .stages-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  list-style: none;
  padding: 10px 0;
  font-size: 0.86rem;
  margin: 0;
}

.stages-panel > .stages-head::-webkit-details-marker {
  display: none;
}

.stages-panel > .stages-head::before {
  content: '▸';
  color: var(--ds-muted);
  font-size: 0.75rem;
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
  color: var(--ds-accent-deep);
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.linkish:hover {
  text-decoration: underline;
}

.run-meta.compact {
  padding: 8px 10px;
  font-size: 0.78rem;
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
  border: 1px solid var(--ds-line);
  border-radius: 10px;
  background: #fff;
  margin-bottom: 8px;
  padding: 0 10px;
}

.stage-fold summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  list-style: none;
  padding: 10px 0;
  font-size: 0.88rem;
}

.stage-fold summary::-webkit-details-marker {
  display: none;
}

.stage-label {
  font-weight: 600;
  color: var(--ds-accent-deep);
}

.stage-steps {
  border-top: 1px dashed var(--ds-line);
  padding: 8px 0 12px;
}

.stage-step {
  padding: 8px 0;
  border-bottom: 1px solid #eef3f1;
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
  font-size: 0.95rem;
}

.ov-block {
  border-top: 1px solid #eef3f1;
  padding: 10px 0;
}

.ov-title {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-weight: 600;
  font-size: 0.82rem;
  margin-bottom: 6px;
  color: var(--ds-ink-soft);
}

.ov-subtitle {
  font-size: 0.75rem;
  color: var(--ds-muted);
  margin: 8px 0 4px;
}

.ix-card {
  border: 1px solid var(--ds-line);
  border-radius: 10px;
  padding: 8px 10px;
  margin: 6px 0;
  background: var(--ds-surface-solid);
  font-size: 0.84rem;
}

.ix-card.is-ask {
  border-color: #fbbf24;
  background: #fffbeb;
}

.ix-card.is-hitl {
  border-color: #fca5a5;
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
  font-size: 0.8rem;
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
  font-size: 0.84rem;
  margin: 4px 0;
}

.ov-tag {
  margin: 0 6px 6px 0;
}

.ov-art {
  display: block;
  width: 100%;
  text-align: left;
  border: none;
  background: var(--ds-surface-solid);
  border-radius: 8px;
  padding: 6px 8px;
  margin: 4px 0;
  cursor: pointer;
  font-size: 0.82rem;
  color: var(--ds-accent-deep);
}

.ov-art:hover {
  background: #ecfdf5;
}
</style>
