<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

type TraceStep = {
  kind: string
  content?: string
  name?: string
  args?: unknown
  id?: string
  tool_call_id?: string
}

type Trace = {
  steps?: TraceStep[]
  pending_writes?: TraceStep[]
  interrupt?: unknown
}

const API = 'http://127.0.0.1:8000'
const question = ref('我的 Outlook 一直登录不上，邮箱是 wei.zhang@contoso.com')
const loading = ref(false)
const useStream = ref(true)
const health = ref('未检查')
const threadId = ref<string | null>(null)
const taskId = ref<string | null>(null)
const status = ref('')
const interrupt = ref<unknown>(null)
const steps = ref<TraceStep[]>([])
const appliedWrites = ref<unknown[]>([])
const liveEvents = ref<string[]>([])

const hasInterrupt = computed(() => Boolean(interrupt.value))

function applyRecord(data: Record<string, unknown>) {
  threadId.value = (data.thread_id as string) || threadId.value
  taskId.value = (data.task_id as string) || taskId.value
  status.value = (data.status as string) || status.value
  interrupt.value = data.interrupt ?? null
  appliedWrites.value = (data.applied_writes as unknown[]) || []
  const trace = data.trace as Trace | undefined
  if (trace?.steps?.length) {
    steps.value = trace.steps
  }
}

async function checkHealth() {
  try {
    const res = await fetch(`${API}/health`)
    const data = await res.json()
    health.value = data.status === 'ok' ? '后端正常' : '异常'
  } catch {
    health.value = '无法连接后端'
  }
}

function stepTagType(kind: string) {
  if (kind === 'tool_call') return 'warning'
  if (kind === 'tool_result') return 'success'
  if (kind === 'user') return 'info'
  if (kind === 'assistant') return ''
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
          interrupt.value = payload
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
        if (e instanceof Error && e.message !== 'stream error' && !String(e).includes('JSON')) {
          // ignore parse blanks
        }
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
  loading.value = true
  appliedWrites.value = []
  try {
    if (useStream.value) {
      await submitStream()
    } else {
      await submitSync()
    }
    ElMessage.success('任务已执行')
  } catch (e) {
    ElMessage.error(`执行失败: ${e instanceof Error ? e.message : e}`)
  } finally {
    loading.value = false
  }
}

async function resume(approved: boolean) {
  if (!threadId.value) return
  loading.value = true
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
    interrupt.value = data.interrupt || null
    ElMessage.success(approved ? '已批准并落库' : '已拒绝')
  } catch (e) {
    ElMessage.error(`恢复失败: ${e instanceof Error ? e.message : e}`)
  } finally {
    loading.value = false
  }
}

checkHealth()
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
        <el-tag v-if="status" size="small">{{ status }}</el-tag>
        <el-tag v-if="useStream" type="warning" size="small">SSE</el-tag>
      </div>
    </header>

    <main class="main">
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
        v-if="hasInterrupt"
        title="需要人工审批"
        type="warning"
        description="检测到高风险写操作（密码重置 / 许可证变更 / 关单 / 升级）。批准后将真正写入 Mock 数据库。"
        show-icon
        :closable="false"
      />

      <el-alert
        v-if="taskId"
        :title="`Task ${taskId} / Thread ${threadId}`"
        type="info"
        show-icon
        :closable="false"
      />

      <section v-if="appliedWrites.length" class="applied">
        <h2>已落库写操作</h2>
        <el-card v-for="(w, i) in appliedWrites" :key="i" shadow="never" class="card">
          <pre>{{ formatArgs(w) }}</pre>
        </el-card>
      </section>

      <section v-if="steps.length" class="trace">
        <h2>执行轨迹</h2>
        <div v-for="(s, i) in steps" :key="i" class="step">
          <div class="step-head">
            <el-tag :type="stepTagType(s.kind)" size="small">{{ s.kind }}</el-tag>
            <strong v-if="s.name" class="tool-name">{{ s.name }}</strong>
          </div>
          <pre v-if="s.args">{{ formatArgs(s.args) }}</pre>
          <pre v-if="s.content">{{ s.content }}</pre>
        </div>
      </section>

      <section v-if="liveEvents.length" class="events">
        <h3>SSE 事件</h3>
        <el-tag
          v-for="(e, i) in liveEvents"
          :key="i"
          size="small"
          class="ev"
        >{{ e }}</el-tag>
      </section>
    </main>
  </div>
</template>

<style scoped>
.page {
  max-width: 860px;
  margin: 0 auto;
  padding: 48px 24px;
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
.main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 32px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.trace h2,
.applied h2 {
  font-size: 1.1rem;
  margin: 8px 0;
}
.step,
.card {
  border-top: 1px solid #e5e7eb;
  padding: 12px 0;
}
.step-head {
  display: flex;
  gap: 8px;
  align-items: center;
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
  margin: 0 0 8px;
  font-size: 0.95rem;
}
.ev {
  margin: 0 6px 6px 0;
}
</style>
