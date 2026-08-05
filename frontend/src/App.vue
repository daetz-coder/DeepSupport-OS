<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { API, apiHeaders } from './api/client'
import { useHealth } from './composables/useHealth'
import { useMcp } from './composables/useMcp'
import { useSkills } from './composables/useSkills'
import type {
  ArtifactItem,
  AuditItem,
  HitlPreview,
  InterruptInfo,
  TaskItem,
  TodoItem,
  Trace,
  TraceStep,
} from './types'

const question = ref('我的 Outlook 一直登录不上，邮箱是 wei.zhang@contoso.com')
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
const steps = ref<TraceStep[]>([])
const appliedWrites = ref<unknown[]>([])
const liveEvents = ref<string[]>([])
const taskList = ref<TaskItem[]>([])
const auditList = ref<AuditItem[]>([])
const todos = ref<TodoItem[]>([])
const artifacts = ref<ArtifactItem[]>([])
const artifactContent = ref<string | null>(null)
const artifactFocus = ref<string | null>(null)
const activeTab = ref('trace')
const lastError = ref<string | null>(null)
const lastQuestion = ref('')

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

function applyRecord(data: Record<string, unknown>) {
  threadId.value = (data.thread_id as string) || threadId.value
  taskId.value = (data.task_id as string) || taskId.value
  status.value = (data.status as string) || status.value
  workspacePath.value = (data.workspace_path as string) || workspacePath.value
  interrupt.value = (data.interrupt as InterruptInfo) || null
  appliedWrites.value = (data.applied_writes as unknown[]) || []
  if (Array.isArray(data.todos)) {
    todos.value = data.todos as TodoItem[]
  }
  if (Array.isArray(data.artifacts)) {
    artifacts.value = data.artifacts as ArtifactItem[]
  }
  const trace = data.trace as Trace | undefined
  if (trace?.steps?.length) {
    steps.value = trace.steps
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
  workspacePath.value = null
  interrupt.value = null
  steps.value = []
  appliedWrites.value = []
  liveEvents.value = []
  todos.value = []
  artifacts.value = []
  artifactContent.value = null
  artifactFocus.value = null
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
    await refreshArtifacts()
    ElMessage.success('已加载历史任务')
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
    activeTab.value = 'artifacts'
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
        if (
          event === 'tool_start' ||
          event === 'tool_end' ||
          event === 'message' ||
          event === 'subagent' ||
          event === 'context_offload'
        ) {
          steps.value = [...steps.value, payload as TraceStep]
        } else if (event === 'todos' && Array.isArray(payload.todos)) {
          todos.value = payload.todos as TodoItem[]
        } else if (event === 'interrupt') {
          interrupt.value = payload as InterruptInfo
          status.value = 'interrupted'
        } else if (event === 'done') {
          applyRecord(payload)
        } else if (event === 'status' && payload.task_id) {
          taskId.value = payload.task_id
          threadId.value = payload.thread_id
          status.value = payload.status || status.value
          if (payload.workspace_path) workspacePath.value = payload.workspace_path
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
    await Promise.all([refreshTasks(), refreshAudit(), refreshArtifacts()])
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
      headers: apiHeaders({ 'Content-Type': 'application/json' }),
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
    await Promise.all([refreshTasks(), refreshAudit(), refreshArtifacts()])
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : String(e)
    ElMessage.error(`恢复失败: ${lastError.value}`)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await checkHealth()
  await Promise.all([refreshTasks(), refreshAudit(), refreshSkills(), refreshMcp()])
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
        <div v-if="status" class="run-status-row">
          <span class="deps-label soft">当前任务</span>
          <span class="status-chip is-run"><i class="dot" />{{ status }}</span>
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

    <main class="layout">
      <aside class="side">
        <div class="side-head">
          <h3>会话</h3>
          <div class="side-actions">
            <el-button size="small" type="primary" @click="newThread">新建</el-button>
            <el-button size="small" plain @click="refreshTasks">刷新</el-button>
          </div>
        </div>
        <div v-if="!taskList.length" class="empty-hint">暂无历史任务</div>
        <button
          v-for="item in taskList"
          :key="item.task_id"
          class="task-item"
          :class="{ active: item.task_id === taskId }"
          type="button"
          @click="openTask(item)"
        >
          <div class="task-meta">
            <el-tag size="small" effect="plain">{{ item.status }}</el-tag>
            <span>{{ item.updated_at?.slice(0, 19) || '' }}</span>
          </div>
          <div class="task-preview">{{ item.preview || item.task_id }}</div>
        </button>
      </aside>

      <section class="main">
        <div class="composer">
          <label class="composer-label">支持请求</label>
          <el-input
            v-model="question"
            type="textarea"
            :rows="3"
            placeholder="例如：我的 Outlook 一直登录不上，邮箱是 wei.zhang@contoso.com"
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
              <el-button type="primary" :loading="loading" @click="submit">
                提交支持任务
              </el-button>
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

        <el-alert
          v-if="hasInterrupt"
          class="panel-alert"
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

        <div v-if="taskId" class="run-meta">
          <span class="meta-k">Task</span>
          <code>{{ taskId }}</code>
          <span class="meta-k">Thread</span>
          <code>{{ threadId }}</code>
          <template v-if="workspacePath">
            <span class="meta-k">Workspace</span>
            <code class="ws">{{ workspacePath }}</code>
          </template>
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
  max-width: 1180px;
  margin: 0 auto;
  padding: 32px 20px 56px;
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
  gap: 16px;
  padding-bottom: 8px;
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

.layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 18px;
  margin-top: 22px;
  align-items: start;
}

@media (max-width: 960px) {
  .layout {
    grid-template-columns: 1fr;
  }
}

.side,
.composer,
.workspace-panel,
.hitl-preview {
  background: var(--ds-panel);
  border: 1px solid var(--ds-line);
  border-radius: var(--ds-radius);
  box-shadow: var(--ds-shadow);
}

.side {
  padding: 14px;
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 32px);
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
  gap: 14px;
  min-width: 0;
}

.composer {
  padding: 16px;
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
</style>
