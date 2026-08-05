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
  font-size: 0.95rem;
  line-height: 1.55;
  color: var(--ds-ink);
}

.md-body :deep(:first-child) {
  margin-top: 0;
}

.md-body :deep(:last-child) {
  margin-bottom: 0;
}

.md-body :deep(p) {
  margin: 0.45em 0;
}

.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3),
.md-body :deep(h4) {
  margin: 0.7em 0 0.35em;
  font-weight: 650;
  line-height: 1.3;
  color: var(--ds-ink);
}

.md-body :deep(h1) {
  font-size: 1.15rem;
}

.md-body :deep(h2) {
  font-size: 1.08rem;
}

.md-body :deep(h3),
.md-body :deep(h4) {
  font-size: 1rem;
}

.md-body :deep(ul),
.md-body :deep(ol) {
  margin: 0.4em 0;
  padding-left: 1.35em;
}

.md-body :deep(li) {
  margin: 0.2em 0;
}

.md-body :deep(li > p) {
  margin: 0.15em 0;
}

.md-body :deep(blockquote) {
  margin: 0.5em 0;
  padding: 0.25em 0.75em;
  border-left: 3px solid var(--ds-line);
  color: var(--ds-ink-soft);
  background: rgba(15, 23, 42, 0.03);
}

.md-body :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.86em;
  padding: 0.1em 0.35em;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.06);
}

.md-body :deep(pre) {
  margin: 0.55em 0;
  padding: 10px 12px;
  overflow-x: auto;
  border-radius: 8px;
  border: 1px solid var(--ds-line);
  background: #0f172a0a;
  font-size: 0.84rem;
  line-height: 1.45;
}

.md-body :deep(pre code) {
  padding: 0;
  background: transparent;
  font-size: inherit;
}

.md-body :deep(a) {
  color: #0f766e;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.md-body :deep(hr) {
  margin: 0.75em 0;
  border: none;
  border-top: 1px solid var(--ds-line);
}

.md-body :deep(table) {
  width: 100%;
  margin: 0.55em 0;
  border-collapse: collapse;
  font-size: 0.88rem;
}

.md-body :deep(th),
.md-body :deep(td) {
  border: 1px solid var(--ds-line);
  padding: 6px 8px;
  text-align: left;
}

.md-body :deep(th) {
  background: rgba(15, 23, 42, 0.04);
  font-weight: 600;
}

.md-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
}
</style>
