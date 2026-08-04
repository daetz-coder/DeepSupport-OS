<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const question = ref('我的 Outlook 一直登录不上，邮箱是 wei.zhang@contoso.com')
const loading = ref(false)
const health = ref('未检查')
const threadId = ref<string | null>(null)
const taskId = ref<string | null>(null)
const messages = ref<{ role: string; content: string }[]>([])
const interrupt = ref<unknown>(null)
const status = ref('')

async function checkHealth() {
  try {
    const res = await fetch('http://127.0.0.1:8000/health')
    const data = await res.json()
    health.value = data.status === 'ok' ? '后端正常' : '异常'
  } catch {
    health.value = '无法连接后端'
  }
}

async function submit() {
  if (!question.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }
  loading.value = true
  interrupt.value = null
  try {
    const res = await fetch('http://127.0.0.1:8000/api/tasks', {
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
    threadId.value = data.thread_id
    taskId.value = data.task_id
    status.value = data.status
    messages.value = data.messages || []
    interrupt.value = data.interrupt
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
    const res = await fetch('http://127.0.0.1:8000/api/tasks/resume', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: threadId.value, approved }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || res.statusText)
    }
    const data = await res.json()
    messages.value = data.messages || []
    interrupt.value = null
    status.value = approved ? 'approved' : 'rejected'
    ElMessage.success(approved ? '已批准继续' : '已拒绝')
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
      <el-tag :type="health.includes('正常') ? 'success' : 'info'" size="small">
        {{ health }}
      </el-tag>
      <el-tag v-if="status" class="ml" size="small">{{ status }}</el-tag>
    </header>

    <main class="main">
      <el-input
        v-model="question"
        type="textarea"
        :rows="3"
        placeholder="例如：我的 Outlook 一直登录不上。"
      />
      <div class="actions">
        <el-button type="primary" :loading="loading" @click="submit">
          提交支持任务
        </el-button>
        <el-button @click="checkHealth">检查后端</el-button>
        <el-button
          v-if="interrupt"
          type="success"
          :loading="loading"
          @click="resume(true)"
        >
          批准继续
        </el-button>
        <el-button
          v-if="interrupt"
          type="danger"
          :loading="loading"
          @click="resume(false)"
        >
          拒绝
        </el-button>
      </div>

      <el-alert
        v-if="taskId"
        :title="`Task ${taskId} / Thread ${threadId}`"
        type="info"
        show-icon
        :closable="false"
      />

      <section v-if="messages.length" class="trace">
        <h2>执行轨迹</h2>
        <div v-for="(m, i) in messages" :key="i" class="msg">
          <strong>{{ m.role }}</strong>
          <pre>{{ m.content }}</pre>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.page {
  max-width: 800px;
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
.ml {
  margin-left: 8px;
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
}
.trace h2 {
  font-size: 1.1rem;
  margin: 8px 0;
}
.msg {
  border-top: 1px solid #e5e7eb;
  padding: 12px 0;
}
.msg pre {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 8px 0 0;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 0.85rem;
  color: #374151;
}
</style>
