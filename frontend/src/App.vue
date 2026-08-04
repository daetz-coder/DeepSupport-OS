<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

type TraceStep = {
  kind: string
  content?: string
  name?: string
  args?: unknown
  id?: string
  tool_call_id?: string
}

type HitlHighlight = { key: string; value: string }
type HitlPreview = {
  name: string
  label: string
  highlights: HitlHighlight[]
  args: Record<string, unknown>
}

type InterruptInfo = {
  next?: string[]
  pending_writes?: TraceStep[]
  pending_preview?: HitlPreview[]
  tasks?: string[]
}

type Trace = {
  steps?: TraceStep[]
  pending_writes?: TraceStep[]
  interrupt?: unknown
}

type TaskItem = {
  task_id: string
  thread_id: string
  status: string
  updated_at?: string
  preview?: string
}

type AuditItem = {
  id: number
  task_id: string
  tool: string
  arguments: string
  result: string
  timestamp?: string
}

type PlanItem = {
  name: string
  status: 'done' | 'pending' | 'running'
  args?: unknown
}

const API = 'http://127.0.0.1:8000'
const question = ref('我的 Outlook 一直登录不上，邮箱是 wei.zhang@contoso.com')
const loading = ref(false)
const useStream = ref(true)
const health = ref('未检查')
const llmConfigured = ref<boolean | null>(null)
const threadId = ref<string | null>(null)
const taskId = ref<string | null>(null)
const status = ref('')
const interrupt = ref<InterruptInfo | null>(null)
const steps = ref<TraceStep[]>([])
const appliedWrites = ref<unknown[]>([])
const liveEvents = ref<string[]>([])
const taskList = ref<TaskItem[]>([])
const auditList = ref<AuditItem[]>([])
const activeTab = ref('trace')
const lastError = ref<string | null>(null)
const lastQuestion = ref('')

const hasInterrupt = computed(() => Boolean(interrupt.value))
const pendingPreview = computed<HitlPreview[]>(() => {
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

const planItems = computed<PlanItem[]>(() => {
  const calls = steps.value.filter((s) => s.kind === 'tool_call' && s.name)
  const results = new Set(
    steps.value
      .filter((s) => s.kind === 'tool_result' && s.name)
      .map((s) => s.name as string),
  )
  const seen = new Set<string>()
  const items: PlanItem[] = []
  for (const c of calls) {
    const name = c.name as string
    if (seen.has(name)) continue
    seen.add(name)
    items.push({
      name,
      status: results.has(name) ? 'done' : loading.value ? 'running' : 'pending',
      args: c.args,
    })
  }
  return items
})

function applyRecord(data: Record<string, unknown>) {
  threadId.value = (data.thread_id as string) || threadId.value
  taskId.value = (data.task_id as string) || taskId.value
  status.value = (data.status as string) || status.value
  interrupt.value = (data.interrupt as InterruptInfo) || null
  appliedWrites.value = (data.applied_writes as unknown[]) || []
  const trace = data.trace as Trace | undefined
  if (trace?.steps?.length) {
    steps.value = trace.steps
  }
}

async function checkHealth() {
  try {
    const res = await fetch(`${API}/`)
    const data = await res.json()
    health.value = '后端正常'
    llmConfigured.value = Boolean(data.llm_configured)
  } catch {
    health.value = '无法连接后端'
    llmConfigured.value = null
  }
}

async function refreshTasks() {
  try {
    const res = await fetch(`${API}/api/tasks?limit=20`)
    if (!res.ok) return
    const data = await res.json()
    taskList.value = data.items || []
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
  interrupt.value = null
  steps.value = []
  appliedWrites.value = []
  liveEvents.value = []
  lastError.value = null
  question.value = ''
  ElMessage.info('已新建会话线程')
}

async function openTask(item: TaskItem) {
  try {
    const res = await fetch(`${API}/api/tasks/${item.task_id}`)
    if (!res.ok) throw new Error('task not found')
    const data = await res.json()
    applyRecord(data)
    lastError.value = null
    activeTab.value = 'trace'
    ElMessage.success('已加载历史任务')
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : String(e)
    ElMessage.error(`加载失败: ${lastError.value}`)
  }
}

function stepTagType(kind: string) {
  if (kind === 'tool_call') return 'warning'
  if (kind === 'tool_result') return 'success'
  if (kind === 'user') return 'info'
  if (kind === 'assistant') return ''
  return 'info'
}

function planTagType(status: PlanItem['status']) {
  if (status === 'done') return 'success'
  if (status === 'running') return 'warning'
  return 'info'
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
    headers: { 'Content-Type': 'application/json' },
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

async function submitStream() {
  liveEvents.value = []
  steps.value = []
  interrupt.value = null
  const res = await fetch(`${API}/api/tasks/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({
      message: question.value,
      thread_id: threadId.value,
    }),
  })
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || res.statusText)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      const lines = part.split('\n')
      let event = 'message'
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (!data) continue
      liveEvents.value.push(`${event}`)
      try {
        const payload = JSON.parse(data)
        if (event === 'tool_start' || event === 'tool_end' || event === 'message') {
          steps.value = [...steps.value, payload as TraceStep]
        } else if (event === 'interrupt') {
          interrupt.value = payload as InterruptInfo
          status.value = 'interrupted'
        } else if (event === 'done') {
          applyRecord(payload)
        } else if (event === 'status' && payload.task_id) {
          taskId.value = payload.task_id
          threadId.value = payload.thread_id
          status.value = payload.status || status.value
        } else if (event === 'error') {
          throw new Error(payload.error || 'stream error')
        }
      } catch (e) {
        if (event === 'error') throw e
      }
    }
  }
}

async function submit() {
  if (!question.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }
  if (llmConfigured.value === false) {
    ElMessage.warning('未配置 LLM（DEEPSEEK_API_KEY），任务可能失败')
  }
  loading.value = true
  lastError.value = null
  lastQuestion.value = question.value
  appliedWrites.value = []
  try {
    if (useStream.value) {
      await submitStream()
    } else {
      await submitSync()
    }
    ElMessage.success('任务已执行')
    await Promise.all([refreshTasks(), refreshAudit()])
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : String(e)
    status.value = 'failed'
    ElMessage.error(`执行失败: ${lastError.value}`)
  } finally {
    loading.value = false
  }
}

async function retryLast() {
  if (lastQuestion.value) {
    question.value = lastQuestion.value
  }
  // New thread for clean retry after failure (avoid polluted checkpoint)
  if (status.value === 'failed') {
    threadId.value = null
    taskId.value = null
  }
  await submit()
}

async function resume(approved: boolean) {
  if (!threadId.value) return
  loading.value = true
  lastError.value = null
  try {
    const res = await fetch(`${API}/api/tasks/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        thread_id: threadId.value,
        task_id: taskId.value,
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
    ElMessage.success(approved ? '已批准并落库' : '已拒绝')
    await Promise.all([refreshTasks(), refreshAudit()])
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : String(e)
    ElMessage.error(`恢复失败: ${lastError.value}`)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await checkHealth()
  await Promise.all([refreshTasks(), refreshAudit()])
})
</script>

<template>
  <div class="page">
    <header class="header">
      <h1>DeepSupport OS</h1>
      <p class="tagline">基于 Deep Agents Harness 的企业 IT 技术支持智能体</p>
      <div class="tags">
        <el-tag :type="health.includes('正常') ? 'success' : 'info'" size="small">
          {{ health }}
        </el-tag>
        <el-tag
          v-if="llmConfigured !== null"
          :type="llmConfigured ? 'success' : 'danger'"
          size="small"
        >
          {{ llmConfigured ? 'LLM 已配置' : 'LLM 未配置' }}
        </el-tag>
        <el-tag v-if="status" size="small">{{ status }}</el-tag>
        <el-tag v-if="useStream" type="warning" size="small">SSE</el-tag>
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

    <main class="layout">
      <aside class="side">
        <div class="side-actions">
          <el-button size="small" type="primary" @click="newThread">新建线程</el-button>
          <el-button size="small" @click="refreshTasks">刷新</el-button>
        </div>
        <h3>会话 / 任务</h3>
        <div v-if="!taskList.length" class="muted">暂无历史任务</div>
        <button
          v-for="item in taskList"
          :key="item.task_id"
          class="task-item"
          type="button"
          @click="openTask(item)"
        >
          <div class="task-meta">
            <el-tag size="small">{{ item.status }}</el-tag>
            <span>{{ item.updated_at?.slice(0, 19) || '' }}</span>
          </div>
          <div class="task-preview">{{ item.preview || item.task_id }}</div>
        </button>
      </aside>

      <section class="main">
        <el-input
          v-model="question"
          type="textarea"
          :rows="3"
          placeholder="例如：我的 Outlook 一直登录不上。"
        />
        <div class="actions">
          <el-checkbox v-model="useStream">流式进度 (SSE)</el-checkbox>
          <el-button type="primary" :loading="loading" @click="submit">
            提交支持任务
          </el-button>
          <el-button
            v-if="lastError"
            type="warning"
            :loading="loading"
            @click="retryLast"
          >
            重试
          </el-button>
          <el-button @click="checkHealth">检查后端</el-button>
          <el-button
            v-if="hasInterrupt"
            type="success"
            :loading="loading"
            @click="resume(true)"
          >
            批准继续
          </el-button>
          <el-button
            v-if="hasInterrupt"
            type="danger"
            :loading="loading"
            @click="resume(false)"
          >
            拒绝
          </el-button>
        </div>

        <el-alert
          v-if="lastError"
          title="任务执行失败"
          type="error"
          :description="lastError"
          show-icon
          :closable="true"
          @close="lastError = null"
        />

        <el-alert
          v-if="hasInterrupt"
          title="需要人工审批"
          type="warning"
          description="高风险写操作待确认。请核对下方参数后批准或拒绝；批准后将写入 Mock 数据库。"
          show-icon
          :closable="false"
        />

        <section v-if="hasInterrupt && pendingPreview.length" class="hitl-preview">
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

        <el-alert
          v-if="taskId"
          :title="`Task ${taskId} / Thread ${threadId}`"
          type="info"
          show-icon
          :closable="false"
        />

        <el-tabs v-model="activeTab">
          <el-tab-pane label="执行计划" name="plan">
            <div v-if="!planItems.length" class="muted">提交任务后将根据工具调用生成计划清单</div>
            <div v-for="(p, i) in planItems" :key="i" class="plan-row">
              <el-tag :type="planTagType(p.status)" size="small">{{ p.status }}</el-tag>
              <strong>{{ p.name }}</strong>
            </div>
          </el-tab-pane>

          <el-tab-pane label="执行轨迹" name="trace">
            <section v-if="appliedWrites.length" class="applied">
              <h2>已落库写操作</h2>
              <el-card v-for="(w, i) in appliedWrites" :key="i" shadow="never" class="card">
                <pre>{{ formatArgs(w) }}</pre>
              </el-card>
            </section>
            <section v-if="steps.length" class="trace">
              <div v-for="(s, i) in steps" :key="i" class="step">
                <div class="step-head">
                  <el-tag :type="stepTagType(s.kind)" size="small">{{ s.kind }}</el-tag>
                  <strong v-if="s.name" class="tool-name">{{ s.name }}</strong>
                </div>
                <pre v-if="s.args">{{ formatArgs(s.args) }}</pre>
                <pre v-if="s.content">{{ s.content }}</pre>
              </div>
            </section>
            <div v-else class="muted">提交任务后将在此显示结构化轨迹</div>
            <section v-if="liveEvents.length" class="events">
              <h3>SSE 事件</h3>
              <el-tag v-for="(e, i) in liveEvents" :key="i" size="small" class="ev">{{ e }}</el-tag>
            </section>
          </el-tab-pane>

          <el-tab-pane label="审计日志" name="audit">
            <el-button size="small" @click="refreshAudit">刷新审计</el-button>
            <div v-if="!auditList.length" class="muted">暂无审计记录</div>
            <div v-for="a in auditList" :key="a.id" class="audit-row">
              <div class="step-head">
                <el-tag size="small">{{ a.tool }}</el-tag>
                <span class="muted">{{ a.timestamp }} · {{ a.task_id }}</span>
              </div>
              <pre>{{ a.result }}</pre>
            </div>
          </el-tab-pane>
        </el-tabs>
      </section>
    </main>
  </div>
</template>

<style scoped>
.page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 40px 24px;
}
.header h1 {
  margin: 0 0 8px;
  font-size: 2rem;
  letter-spacing: -0.02em;
}
.tagline {
  margin: 0 0 12px;
  color: #606266;
}
.tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.banner {
  margin-top: 16px;
}
.layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 20px;
  margin-top: 24px;
}
@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
.side {
  border-right: 1px solid #e5e7eb;
  padding-right: 12px;
}
.side h3 {
  margin: 12px 0 8px;
  font-size: 0.95rem;
}
.side-actions {
  display: flex;
  gap: 8px;
}
.task-item {
  width: 100%;
  text-align: left;
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
  cursor: pointer;
}
.task-item:hover {
  border-color: #93c5fd;
}
.task-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 0.75rem;
  color: #6b7280;
  margin-bottom: 6px;
}
.task-preview {
  font-size: 0.85rem;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.main {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.trace h2,
.applied h2,
.hitl-preview h2 {
  font-size: 1.05rem;
  margin: 8px 0;
}
.hitl-preview {
  border: 1px solid #fbbf24;
  background: #fffbeb;
  border-radius: 8px;
  padding: 12px 14px;
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
.plan-row {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f3f4f6;
}
.step,
.card,
.audit-row {
  border-top: 1px solid #e5e7eb;
  padding: 12px 0;
}
.step-head {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.tool-name {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 0.9rem;
}
pre {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 8px 0 0;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 0.85rem;
  color: #374151;
}
.events h3 {
  margin: 8px 0;
  font-size: 0.95rem;
}
.ev {
  margin: 0 6px 6px 0;
}
.muted {
  color: #9ca3af;
  font-size: 0.85rem;
}
</style>
