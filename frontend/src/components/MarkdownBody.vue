<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps<{
  source: string
}>()

const html = computed(() => renderMarkdown(props.source))
</script>

<template>
  <div class="md-body" v-html="html" />
</template>

<style scoped>
.md-body {
  word-break: break-word;
  font-size: 14px;
  line-height: 1.6;
  color: var(--fg-primary);
}

.md-body :deep(:first-child) {
  margin-top: 0;
}

.md-body :deep(:last-child) {
  margin-bottom: 0;
}

.md-body :deep(p) {
  margin: 0.5em 0;
}

.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3),
.md-body :deep(h4) {
  margin: 0.75em 0 0.4em;
  font-weight: 600;
  line-height: 1.3;
  color: var(--fg-primary);
}

.md-body :deep(h1) {
  font-size: 18px;
}

.md-body :deep(h2) {
  font-size: 16px;
}

.md-body :deep(h3),
.md-body :deep(h4) {
  font-size: 14px;
}

.md-body :deep(ul),
.md-body :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.md-body :deep(li) {
  margin: 0.25em 0;
}

.md-body :deep(li > p) {
  margin: 0.2em 0;
}

.md-body :deep(blockquote) {
  margin: 0.6em 0;
  padding: 0.3em 0.8em;
  border-left: 3px solid var(--border-strong);
  color: var(--fg-secondary);
  background: var(--bg-sidebar);
}

.md-body :deep(code) {
  font-family: var(--font-mono);
  font-size: 12px;
  padding: 0.15em 0.4em;
  border-radius: 4px;
  background: var(--bg-sidebar);
  color: var(--accent);
}

.md-body :deep(pre) {
  margin: 0.6em 0;
  padding: 12px 14px;
  overflow-x: auto;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-sidebar);
  font-size: 13px;
  line-height: 1.5;
}

.md-body :deep(pre code) {
  padding: 0;
  background: transparent;
  font-size: inherit;
  color: var(--fg-primary);
}

.md-body :deep(a) {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.md-body :deep(a:hover) {
  color: #0051d5;
}

.md-body :deep(hr) {
  margin: 0.8em 0;
  border: none;
  border-top: 1px solid var(--border);
}

.md-body :deep(table) {
  width: 100%;
  margin: 0.6em 0;
  border-collapse: collapse;
  font-size: 13px;
}

.md-body :deep(th),
.md-body :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
}

.md-body :deep(th) {
  background: var(--bg-sidebar);
  font-weight: 600;
}

.md-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-sm);
}
</style>
