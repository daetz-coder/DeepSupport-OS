<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { API } from '../api/client'

const props = defineProps<{
  taskId: string
}>()

interface TimelineTree {
  id: string
  name: string
  kind: string
  parent_id: string | null
  start_time: number
  end_time: number | null
  duration_ms: number | null
  status: string
  metadata: Record<string, any>
  children: TimelineTree[]
}

const timeline = ref<TimelineTree | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const expandedSpans = ref<Set<string>>(new Set())

// Color scheme for different span kinds
const kindColors: Record<string, string> = {
  agent: '#3b82f6',      // blue
  subagent: '#8b5cf6',   // purple
  tool: '#10b981',       // green
  skill: '#f59e0b',      // yellow
  llm: '#ec4899',        // pink
}

// Status colors
const statusColors: Record<string, string> = {
  running: '#3b82f6',    // blue
  completed: '#10b981',  // green
  failed: '#ef4444',     // red
  timeout: '#f59e0b',    // yellow
}

const fetchTimeline = async () => {
  if (!props.taskId) return
  
  loading.value = true
  error.value = null
  
  try {
    const res = await fetch(`${API}/api/tasks/${props.taskId}/timeline/tree`)
    if (!res.ok) {
      throw new Error(`Failed to fetch timeline: ${res.statusText}`)
    }
    timeline.value = await res.json()
    
    // Auto-expand all spans initially
    if (timeline.value) {
      expandAll(timeline.value)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load timeline'
  } finally {
    loading.value = false
  }
}

const expandAll = (node: TimelineTree) => {
  expandedSpans.value.add(node.id)
  if (node.children) {
    node.children.forEach(expandAll)
  }
}

const collapseAll = () => {
  expandedSpans.value.clear()
}

const toggleSpan = (spanId: string) => {
  if (expandedSpans.value.has(spanId)) {
    expandedSpans.value.delete(spanId)
  } else {
    expandedSpans.value.add(spanId)
  }
}

const isExpanded = (spanId: string) => {
  return expandedSpans.value.has(spanId)
}

const formatTime = (timestamp: number) => {
  const date = new Date(timestamp * 1000)
  return date.toLocaleTimeString('zh-CN', { 
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3
  })
}

const formatDuration = (durationMs: number | null) => {
  if (durationMs === null) return '-'
  if (durationMs < 1000) {
    return `${Math.round(durationMs)}ms`
  }
  return `${(durationMs / 1000).toFixed(2)}s`
}

const getKindColor = (kind: string) => {
  return kindColors[kind] || '#6b7280'
}

const getStatusColor = (status: string) => {
  return statusColors[status] || '#6b7280'
}

const totalDuration = computed(() => {
  if (!timeline.value) return null
  return timeline.value.duration_ms
})

// Fetch timeline on mount and when taskId changes
onMounted(fetchTimeline)
watch(() => props.taskId, fetchTimeline)

// Auto-refresh every 2 seconds if task is running
const isRunning = computed(() => {
  return timeline.value?.status === 'running'
})

let refreshInterval: number | null = null

watch(isRunning, (running) => {
  if (running) {
    refreshInterval = window.setInterval(fetchTimeline, 2000)
  } else if (refreshInterval) {
    clearInterval(refreshInterval)
    refreshInterval = null
  }
})
</script>

<template>
  <div class="timeline-view">
    <div class="timeline-header">
      <div class="timeline-actions">
        <button @click="expandAll(timeline!)" :disabled="!timeline">全部展开</button>
        <button @click="collapseAll" :disabled="!timeline">全部折叠</button>
        <button @click="fetchTimeline" :disabled="loading">
          {{ loading ? '加载中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="timeline-error">
      {{ error }}
    </div>

    <div v-else-if="!timeline" class="timeline-empty">
      暂无时间线数据
    </div>

    <div v-else class="timeline-content">
      <div class="timeline-summary">
        <div class="summary-item">
          <span class="summary-label">总耗时:</span>
          <span class="summary-value">{{ formatDuration(totalDuration) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">状态:</span>
          <span class="summary-status" :style="{ color: getStatusColor(timeline.status) }">
            {{ timeline.status }}
          </span>
        </div>
      </div>

      <div class="timeline-tree">
        <div class="timeline-span" :style="{ '--span-color': getKindColor(timeline.kind) }">
          <div class="span-header" @click="toggleSpan(timeline.id)">
            <span class="span-toggle" v-if="timeline.children && timeline.children.length > 0">
              {{ isExpanded(timeline.id) ? '▼' : '▶' }}
            </span>
            <span v-else class="span-toggle-placeholder"></span>
            
            <span class="span-kind" :style="{ backgroundColor: getKindColor(timeline.kind) }">
              {{ timeline.kind }}
            </span>
            
            <span class="span-name">{{ timeline.name }}</span>
            
            <span class="span-time">{{ formatTime(timeline.start_time) }}</span>
            
            <span class="span-duration">{{ formatDuration(timeline.duration_ms) }}</span>
            
            <span class="span-status" :style="{ color: getStatusColor(timeline.status) }">
              {{ timeline.status }}
            </span>
          </div>

          <div v-if="isExpanded(timeline.id) && timeline.children" class="span-children">
            <div 
              v-for="child in timeline.children" 
              :key="child.id"
              class="timeline-span nested"
              :style="{ '--span-color': getKindColor(child.kind) }"
            >
              <div class="span-header" @click="toggleSpan(child.id)">
                <span class="span-toggle" v-if="child.children && child.children.length > 0">
                  {{ isExpanded(child.id) ? '▼' : '▶' }}
                </span>
                <span v-else class="span-toggle-placeholder"></span>
                
                <span class="span-kind" :style="{ backgroundColor: getKindColor(child.kind) }">
                  {{ child.kind }}
                </span>
                
                <span class="span-name">{{ child.name }}</span>
                
                <span class="span-time">{{ formatTime(child.start_time) }}</span>
                
                <span class="span-duration">{{ formatDuration(child.duration_ms) }}</span>
                
                <span class="span-status" :style="{ color: getStatusColor(child.status) }">
                  {{ child.status }}
                </span>
              </div>

              <div v-if="isExpanded(child.id) && child.children" class="span-children">
                <!-- Recursive children would go here -->
                <div 
                  v-for="grandchild in child.children" 
                  :key="grandchild.id"
                  class="timeline-span nested"
                  :style="{ '--span-color': getKindColor(grandchild.kind) }"
                >
                  <div class="span-header" @click="toggleSpan(grandchild.id)">
                    <span class="span-toggle-placeholder"></span>
                    
                    <span class="span-kind" :style="{ backgroundColor: getKindColor(grandchild.kind) }">
                      {{ grandchild.kind }}
                    </span>
                    
                    <span class="span-name">{{ grandchild.name }}</span>
                    
                    <span class="span-time">{{ formatTime(grandchild.start_time) }}</span>
                    
                    <span class="span-duration">{{ formatDuration(grandchild.duration_ms) }}</span>
                    
                    <span class="span-status" :style="{ color: getStatusColor(grandchild.status) }">
                      {{ grandchild.status }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline-view {
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.timeline-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.timeline-actions {
  display: flex;
  gap: 8px;
}

.timeline-actions button {
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.timeline-actions button:hover:not(:disabled) {
  background: #f3f4f6;
}

.timeline-actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.timeline-error {
  padding: 12px;
  background: #fef2f2;
  color: #dc2626;
  border-radius: 4px;
}

.timeline-empty {
  padding: 24px;
  text-align: center;
  color: #6b7280;
}

.timeline-content {
  background: white;
  border-radius: 6px;
  padding: 16px;
}

.timeline-summary {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.summary-item {
  display: flex;
  gap: 8px;
}

.summary-label {
  color: #6b7280;
  font-size: 13px;
}

.summary-value {
  font-weight: 600;
  font-size: 13px;
}

.summary-status {
  font-weight: 600;
  font-size: 13px;
}

.timeline-tree {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', monospace;
  font-size: 13px;
}

.timeline-span {
  margin-bottom: 4px;
}

.timeline-span.nested {
  margin-left: 24px;
  margin-top: 4px;
}

.span-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-left: 2px solid var(--span-color, #6b7280);
  cursor: pointer;
  border-radius: 2px;
}

.span-header:hover {
  background: #f9fafb;
}

.span-toggle {
  width: 16px;
  text-align: center;
  font-size: 10px;
  color: #6b7280;
}

.span-toggle-placeholder {
  width: 16px;
}

.span-kind {
  padding: 2px 6px;
  border-radius: 3px;
  color: white;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  min-width: 60px;
  text-align: center;
}

.span-name {
  flex: 1;
  font-weight: 500;
}

.span-time {
  color: #6b7280;
  font-size: 12px;
  min-width: 100px;
}

.span-duration {
  color: #6b7280;
  font-size: 12px;
  min-width: 80px;
  text-align: right;
}

.span-status {
  font-weight: 600;
  font-size: 12px;
  min-width: 80px;
  text-align: right;
}

.span-children {
  margin-top: 4px;
}
</style>
