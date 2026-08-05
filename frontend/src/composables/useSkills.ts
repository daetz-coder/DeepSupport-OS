import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { API, apiHeaders } from '../api/client'
import type { CatalogEntry, SkillItem } from '../types'

export function useSkills() {
  const skillsInstalled = ref<SkillItem[]>([])
  const skillsCatalog = ref<CatalogEntry[]>([])
  const skillsImportedEnabled = ref(true)
  const skillsBusy = ref(false)

  async function refreshSkills() {
    try {
      const res = await fetch(`${API}/api/meta/skills`)
      if (!res.ok) return
      const data = await res.json()
      skillsInstalled.value = data.installed || []
      skillsCatalog.value = data.catalog?.entries || []
      skillsImportedEnabled.value = Boolean(data.settings?.skills_imported_enabled ?? true)
    } catch {
      /* ignore */
    }
  }

  async function toggleSkill(item: SkillItem, enabled: boolean) {
    skillsBusy.value = true
    try {
      const res = await fetch(`${API}/api/meta/skills/${encodeURIComponent(item.dir_name)}/toggle`, {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ enabled }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || res.statusText)
      }
      ElMessage.success(enabled ? `已启用 ${item.name}` : `已禁用 ${item.name}`)
      await refreshSkills()
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : String(e))
    } finally {
      skillsBusy.value = false
    }
  }

  async function setImportedLayer(enabled: boolean) {
    skillsBusy.value = true
    try {
      const res = await fetch(`${API}/api/meta/skills/settings`, {
        method: 'PATCH',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ skills_imported_enabled: enabled }),
      })
      if (!res.ok) throw new Error('update failed')
      skillsImportedEnabled.value = enabled
      ElMessage.success(enabled ? '已开启 imported 层' : '已关闭 imported 层')
      await refreshSkills()
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : String(e))
    } finally {
      skillsBusy.value = false
    }
  }

  async function importCatalogSkill(entry: CatalogEntry) {
    if (entry.source === 'cli') {
      ElMessage.info(entry.install || '请使用 CLI 安装后复制到 skills/imported/')
      return
    }
    const needLicense = (entry.license || '').toLowerCase().includes('proprietary')
    skillsBusy.value = true
    try {
      const res = await fetch(`${API}/api/meta/skills/import`, {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          catalog_id: entry.id,
          accept_license: needLicense,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || res.statusText)
      }
      ElMessage.success(`已导入 ${entry.name}`)
      await refreshSkills()
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : String(e))
    } finally {
      skillsBusy.value = false
    }
  }

  return {
    skillsInstalled,
    skillsCatalog,
    skillsImportedEnabled,
    skillsBusy,
    refreshSkills,
    toggleSkill,
    setImportedLayer,
    importCatalogSkill,
  }
}
