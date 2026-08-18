import { ref } from 'vue'
import { API } from '../api/client'

export function useHealth() {
  const health = ref('未检查')
  const llmConfigured = ref<boolean | null>(null)
  const raglabOk = ref<boolean | null>(null)
  const raglabLabel = ref('RAGLab 未检查')
  const raglabHint = ref('')
  const sandboxOk = ref<boolean | null>(null)
  const sandboxLabel = ref('Sandbox 未检查')
  const healthChecking = ref(false)

  async function checkHealth() {
    healthChecking.value = true
    try {
      try {
        const res = await fetch(`${API}/health`)
        const data = await res.json()
        health.value = data.status === 'ok' ? '后端正常' : '后端异常'
        llmConfigured.value = Boolean(data.llm_configured)
      } catch {
        health.value = '无法连接后端'
        llmConfigured.value = null
        raglabOk.value = null
        sandboxOk.value = null
        raglabLabel.value = 'RAGLab 未检查'
        raglabHint.value = ''
        sandboxLabel.value = 'Sandbox 未检查'
        return
      }

      try {
        const res = await fetch(`${API}/api/health/deps`)
        const data = await res.json()
        const rag = data.raglab || {}
        raglabOk.value = Boolean(rag.ok)
        raglabHint.value = rag.ok ? '' : String(rag.hint || '')
        if (rag.ok) {
          raglabLabel.value = 'RAGLab 正常'
        } else if (raglabHint.value) {
          raglabLabel.value = 'RAG 已降级（内存不足）'
        } else {
          raglabLabel.value = 'RAGLab 未启动，已回退本地知识'
        }

        const sb = data.sandbox || {}
        sandboxOk.value = Boolean(sb.ok)
        if (sb.ok) {
          sandboxLabel.value = `Sandbox 正常${sb.state ? `（${sb.state}）` : ''}`
        } else if (sb.status === 'disabled') {
          sandboxLabel.value = 'Sandbox 已关闭'
          sandboxOk.value = null
        } else if (sb.status === 'unconfigured') {
          sandboxLabel.value = 'Sandbox 未配置 Key'
        } else if (sb.status === 'stopped') {
          sandboxLabel.value = 'Sandbox 未运行'
        } else {
          const detail = sb.detail ? `（${String(sb.detail).slice(0, 40)}）` : ''
          sandboxLabel.value = `Sandbox 不可用${detail}`
        }
      } catch {
        raglabOk.value = false
        sandboxOk.value = false
        raglabHint.value = ''
        raglabLabel.value = 'RAGLab 探测失败'
        sandboxLabel.value = 'Sandbox 探测失败'
      }
    } finally {
      healthChecking.value = false
    }
  }

  return {
    health,
    llmConfigured,
    raglabOk,
    raglabLabel,
    raglabHint,
    sandboxOk,
    sandboxLabel,
    healthChecking,
    checkHealth,
  }
}
