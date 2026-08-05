import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { API, apiHeaders } from '../api/client'
import type { McpServerSpec } from '../types'

export function useMcp() {
  const mcpLocalTools = ref(true)
  const mcpRemoteEnabled = ref(false)
  const mcpServers = ref<Record<string, McpServerSpec>>({})
  const mcpRuntime = ref<Record<string, unknown>>({})
  const mcpBusy = ref(false)
  const newMcpName = ref('')
  const newMcpUrl = ref('http://127.0.0.1:8100/mcp')
  const newMcpTransport = ref('streamable_http')
  const newMcpDesc = ref('')

  async function refreshMcp() {
    try {
      const res = await fetch(`${API}/api/meta/mcp`)
      if (!res.ok) return
      const data = await res.json()
      mcpLocalTools.value = Boolean(data.settings?.mcp_local_tools ?? true)
      mcpRemoteEnabled.value = Boolean(data.settings?.mcp_remote_enabled ?? false)
      mcpServers.value = data.config_servers || {}
      mcpRuntime.value = data.runtime || {}
    } catch {
      /* ignore */
    }
  }

  async function patchMcpSettings(patch: { mcp_local_tools?: boolean; mcp_remote_enabled?: boolean }) {
    mcpBusy.value = true
    try {
      const res = await fetch(`${API}/api/meta/mcp/settings`, {
        method: 'PATCH',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(patch),
      })
      if (!res.ok) throw new Error('update failed')
      ElMessage.success('MCP 设置已保存（下次任务生效）')
      await refreshMcp()
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : String(e))
    } finally {
      mcpBusy.value = false
    }
  }

  async function toggleMcpServer(name: string, enabled: boolean) {
    mcpBusy.value = true
    try {
      const res = await fetch(`${API}/api/meta/mcp/servers/${encodeURIComponent(name)}/toggle`, {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ enabled }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || res.statusText)
      }
      await refreshMcp()
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : String(e))
    } finally {
      mcpBusy.value = false
    }
  }

  async function addMcpServer() {
    if (!newMcpName.value.trim() || !newMcpUrl.value.trim()) {
      ElMessage.warning('请填写名称与 URL')
      return
    }
    mcpBusy.value = true
    try {
      const res = await fetch(`${API}/api/meta/mcp/servers`, {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          name: newMcpName.value.trim(),
          transport: newMcpTransport.value,
          url: newMcpUrl.value.trim(),
          description: newMcpDesc.value.trim(),
          enabled: true,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || res.statusText)
      }
      ElMessage.success('已添加 MCP Server')
      newMcpName.value = ''
      newMcpDesc.value = ''
      await refreshMcp()
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : String(e))
    } finally {
      mcpBusy.value = false
    }
  }

  async function removeMcpServer(name: string) {
    mcpBusy.value = true
    try {
      const res = await fetch(`${API}/api/meta/mcp/servers/${encodeURIComponent(name)}`, {
        method: 'DELETE',
        headers: apiHeaders(),
      })
      if (!res.ok) throw new Error('delete failed')
      ElMessage.success(`已删除 ${name}`)
      await refreshMcp()
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : String(e))
    } finally {
      mcpBusy.value = false
    }
  }

  async function reloadMcp() {
    mcpBusy.value = true
    try {
      const res = await fetch(`${API}/api/meta/mcp/reload`, { method: 'POST', headers: apiHeaders() })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.detail || 'reload failed')
      ElMessage.success(`已重载，工具数 ${data.tool_count ?? 0}`)
      await refreshMcp()
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : String(e))
    } finally {
      mcpBusy.value = false
    }
  }

  return {
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
  }
}
