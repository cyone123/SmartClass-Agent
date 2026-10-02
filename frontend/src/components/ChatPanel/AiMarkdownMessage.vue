<template>
  <div class="ai-markdown-message" v-html="renderedHtml"></div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'

import 'katex/dist/katex.min.css'

import { renderMarkdown } from './markdown'

const RENDER_INTERVAL_MS = 40

const props = defineProps({
  content: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['rendered'])

const renderedHtml = ref('')

let pendingContent = ''
let timerId = null
let frameId = null
let lastRenderAt = 0

const cancelScheduledRender = () => {
  if (timerId !== null) {
    window.clearTimeout(timerId)
    timerId = null
  }

  if (frameId !== null) {
    window.cancelAnimationFrame(frameId)
    frameId = null
  }
}

const flushRender = () => {
  frameId = window.requestAnimationFrame(() => {
    frameId = null
    renderedHtml.value = renderMarkdown(pendingContent)
    lastRenderAt = performance.now()
    emit('rendered')
  })
}

const scheduleRender = (content) => {
  pendingContent = content ?? ''

  if (timerId !== null || frameId !== null) {
    return
  }

  const elapsed = performance.now() - lastRenderAt
  if (elapsed >= RENDER_INTERVAL_MS) {
    flushRender()
    return
  }

  timerId = window.setTimeout(() => {
    timerId = null
    flushRender()
  }, RENDER_INTERVAL_MS - elapsed)
}

watch(
  () => props.content,
  (content) => {
    scheduleRender(content)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  cancelScheduledRender()
})
</script>

<style scoped>
.ai-markdown-message {
  min-width: 0;
  width: 100%;
  color: inherit;
  line-height: 1.7;
  overflow: hidden;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.ai-markdown-message :deep(p),
.ai-markdown-message :deep(ul),
.ai-markdown-message :deep(ol),
.ai-markdown-message :deep(pre),
.ai-markdown-message :deep(blockquote),
.ai-markdown-message :deep(table),
.ai-markdown-message :deep(.katex-display) {
  margin: 0 0 0.85em;
}

.ai-markdown-message :deep(h1),
.ai-markdown-message :deep(h2),
.ai-markdown-message :deep(h3),
.ai-markdown-message :deep(h4),
.ai-markdown-message :deep(h5),
.ai-markdown-message :deep(h6) {
  margin: 0 0 0.7em;
  line-height: 1.35;
  font-weight: 600;
  color: inherit;
}

.ai-markdown-message :deep(h1) {
  font-size: 1.3em;
}

.ai-markdown-message :deep(h2) {
  font-size: 1.18em;
}

.ai-markdown-message :deep(h3) {
  font-size: 1.08em;
}

.ai-markdown-message :deep(ul),
.ai-markdown-message :deep(ol) {
  padding-left: 1.4em;
}

.ai-markdown-message :deep(li + li) {
  margin-top: 0.3em;
}

.ai-markdown-message :deep(a) {
  color: var(--primary-color);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.ai-markdown-message :deep(strong) {
  font-weight: 600;
}

.ai-markdown-message :deep(code) {
  font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
}

.ai-markdown-message :deep(p code),
.ai-markdown-message :deep(li code),
.ai-markdown-message :deep(blockquote code),
.ai-markdown-message :deep(td code) {
  padding: 0.15em 0.4em;
  border-radius: 6px;
  background-color: #f1f5f9;
  color: #0f172a;
  font-size: 0.92em;
}

.ai-markdown-message :deep(pre) {
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: #0f172a;
  color: #e2e8f0;
  overflow-x: hidden;
}

.ai-markdown-message :deep(pre code) {
  display: block;
  max-width: 100%;
  min-width: 0;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  font-size: 0.9em;
  line-height: 1.6;
}

.ai-markdown-message :deep(blockquote) {
  padding-left: 12px;
  border-left: 3px solid #cbd5e1;
  color: #475569;
}

.ai-markdown-message :deep(table) {
  display: block;
  width: 100%;
  border-collapse: collapse;
  overflow-x: auto;
}

.ai-markdown-message :deep(th),
.ai-markdown-message :deep(td) {
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: top;
}

.ai-markdown-message :deep(th) {
  background-color: #f8fafc;
  font-weight: 600;
}

.ai-markdown-message :deep(hr) {
  margin: 1em 0;
  border: none;
  border-top: 1px solid #e2e8f0;
}

.ai-markdown-message :deep(h1:last-child),
.ai-markdown-message :deep(h2:last-child),
.ai-markdown-message :deep(h3:last-child),
.ai-markdown-message :deep(h4:last-child),
.ai-markdown-message :deep(h5:last-child),
.ai-markdown-message :deep(h6:last-child),
.ai-markdown-message :deep(p:last-child),
.ai-markdown-message :deep(ul:last-child),
.ai-markdown-message :deep(ol:last-child),
.ai-markdown-message :deep(pre:last-child),
.ai-markdown-message :deep(blockquote:last-child),
.ai-markdown-message :deep(table:last-child),
.ai-markdown-message :deep(.katex-display:last-child) {
  margin-bottom: 0;
}

.ai-markdown-message :deep(.katex) {
  max-width: 100%;
}

.ai-markdown-message :deep(.katex-display) {
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 0.15em;
}
</style>
