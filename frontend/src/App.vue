<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const question = ref('')
const loading = ref(false)
const health = ref<string>('未检查')

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
  ElMessage.info('Agent 任务接口将在后续 Phase 接入')
  loading.value = false
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
      </div>
      <el-alert
        title="Phase 0 骨架"
        type="info"
        description="当前仅连通性壳；计划、工具轨迹、HITL 审批将在后续 Phase 接入。"
        show-icon
        :closable="false"
      />
    </main>
  </div>
</template>

<style scoped>
.page {
  max-width: 720px;
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
.main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 32px;
}
.actions {
  display: flex;
  gap: 8px;
}
</style>
