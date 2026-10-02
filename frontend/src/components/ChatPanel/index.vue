<template>
  <div class="chat-container">
    <div class="chat-header">
      <h3>教学对话</h3>
      <div class="header-actions">
        <button class="icon-btn"><MessageSquareShare class="share-btn-icon" /></button>
        <button class="icon-btn"><MoreHorizontal class="btn-icon" /></button>
      </div>
    </div>

    <div class="chat-body" ref="chatBodyRef" @scroll="handleChatScroll">
      <div v-if="messages.length === 0" class="placeholder">
        <div class="empty-state">
          <div class="empty-icon-wrapper">
            <MessageSquarePlus class="empty-icon" />
          </div>
          <p>当前暂无对话，请在下方输入您的需求</p>
          <span class="empty-hint">您可以让我生成教学设计、PPT、教案草稿，或结合附件进行分析。</span>
        </div>
      </div>

      <div v-else class="message-list">
        <template v-for="(msg, index) in messages" :key="msg.runId ? `${msg.runId}_${index}` : index">
          <div
            v-if="shouldRenderMessage(msg)"
            class="message-wrapper"
            :class="msg.role === 'teacher' ? 'message-right' : 'message-left'"
          >
            <div class="avatar" :class="msg.role">
              <User v-if="msg.role === 'teacher'" class="avatar-icon" />
              <Bot v-else class="avatar-icon" />
            </div>

          <div class="message-content">
            <template v-if="!msg.type || msg.type === 'text'">
              <div
                v-if="msg.content || msg.isPending"
                class="message-bubble"
                :class="{ 'is-pending': msg.isPending }"
              >
                <div
                  v-if="msg.isPending"
                  class="message-waiting-dots waiting-dots"
                  aria-label="AI 正在组织回复"
                >
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <template v-else>
                  <AiMarkdownMessage
                    v-if="msg.role === 'ai'"
                    :content="normalizeMessageContent(msg.content)"
                    @rendered="handleAiMessageRendered"
                  />
                  <div v-else class="message-text-content">
                    {{ normalizeMessageContent(msg.content) }}
                  </div>
                </template>
              </div>
            </template>

            <template v-else-if="msg.type === 'progress-status'">
              <div class="progress-status-card" :class="{ 'is-complete': msg.isComplete }">
                <div class="progress-status-header">
                  <span class="progress-status-title">
                    {{ msg.isComplete ? 'Agent 运行完成' : 'Agent 正在处理中' }}
                  </span>
                </div>

                <div class="progress-step-list">
                  <div
                    v-for="step in msg.steps"
                    :key="step.step_key"
                    class="progress-step-item"
                    :class="`is-${step.status}`"
                  >
                    <div class="progress-step-indicator">
                      <div v-if="step.status === 'running'" class="waiting-dots" aria-hidden="true">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                      <Check v-else-if="step.status === 'success'" class="step-icon success" />
                      <AlertCircle v-else-if="step.status === 'failed'" class="step-icon failed" />
                      <span v-else class="step-dot"></span>
                    </div>

                    <div class="progress-step-body">
                      <div class="progress-step-label">{{ step.label }}</div>
                      <div v-if="step.detail" class="progress-step-detail">{{ step.detail }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </template>

            <template v-else-if="msg.type === 'artifact-trace-group'">
              <div class="artifact-trace-group">
                <div class="artifact-trace-group-header">产物生成过程</div>
                <div class="artifact-trace-card-row">
                  <div
                    v-for="card in msg.cards"
                    :key="card.artifactRunId"
                    class="artifact-trace-card"
                    :class="`is-${card.status || 'running'}`"
                  >
                    <div class="artifact-trace-card-header">
                      <div class="artifact-trace-card-title">{{ getArtifactTraceCardTitle(card) }}</div>
                      <div class="artifact-trace-card-status">
                        {{ getArtifactTraceStatusLabel(card) }}
                      </div>
                    </div>

                    <div class="artifact-trace-card-subtitle">
                      {{ getArtifactTraceModeLabel(card.mode) }}
                    </div>

                    <div class="artifact-trace-timeline">
                      <div
                        v-for="entry in card.entries"
                        :key="entry.entryId"
                        class="artifact-trace-item"
                        :class="[
                          `kind-${entry.kind || 'status'}`,
                          `status-${entry.status || 'idle'}`
                        ]"
                      >
                        <div class="artifact-trace-marker">
                          <span class="artifact-trace-dot"></span>
                        </div>

                        <div class="artifact-trace-body">
                          <div class="artifact-trace-entry-header">
                            <div class="artifact-trace-entry-title">
                              {{ entry.title || getArtifactTraceEntryKindLabel(entry.kind) }}
                            </div>
                            <button
                              type="button"
                              class="artifact-trace-toggle"
                              :disabled="!canToggleArtifactTraceEntry(entry)"
                              @click="toggleArtifactTraceEntry(entry)"
                            >
                              <ChevronDown
                                v-if="isArtifactTraceEntryExpanded(entry)"
                                class="artifact-trace-toggle-icon"
                              />
                              <ChevronRight v-else class="artifact-trace-toggle-icon" />
                              <span>{{ getArtifactTraceToggleLabel(entry) }}</span>
                            </button>
                          </div>
                          <div
                            v-if="entry.content && isArtifactTraceEntryExpanded(entry)"
                            class="artifact-trace-entry-content"
                          >
                            {{ entry.content }}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>

            <template v-else-if="msg.type === 'approval-card'">
              <div
                class="approval-card"
                :class="{
                  'is-awaiting-feedback': msg.state === 'awaiting-feedback',
                  'is-resolved': msg.state === 'resolved'
                }"
              >
                <div class="approval-card-header">
                  <div class="approval-card-title">{{ getApprovalTitle(msg) }}</div>
                  <div class="approval-card-desc">{{ getApprovalDescription(msg) }}</div>
                </div>

                <div
                  v-if="
                    msg.approval?.stage === 'metadata_review' &&
                    getApprovalMetadataEntries(msg).length > 0
                  "
                  class="approval-metadata-grid"
                >
                  <div
                    v-for="field in getApprovalMetadataEntries(msg)"
                    :key="field.key"
                    class="approval-metadata-item"
                  >
                    <div class="approval-metadata-label">{{ field.label }}</div>
                    <div class="approval-metadata-value">
                      {{ formatDynamicApprovalMetadataValue(field.value) }}
                    </div>
                  </div>
                </div>

                <div v-if="msg.state === 'awaiting-feedback'" class="approval-feedback-hint">
                  流程已暂停，请输入补充内容或修改建议后重新生成。
                </div>

                <div
                  v-if="msg.approval?.stage === 'teaching_plan_review'"
                  class="approval-artifact-selector"
                >
                  <div class="approval-selector-title">选择要生成的产物</div>
                  <label
                    v-for="option in getApprovalArtifactOptions(msg)"
                    :key="option.type"
                    class="approval-selector-option"
                    :class="{
                      'is-selected': isArtifactOptionSelected(msg, option.type),
                      'is-disabled':
                        !isApprovalCardActionable(index) || msg.state === 'resolved' || isStreaming
                    }"
                  >
                    <input
                      type="checkbox"
                      class="approval-selector-native"
                      :checked="isArtifactOptionSelected(msg, option.type)"
                      :disabled="
                        !isApprovalCardActionable(index) || msg.state === 'resolved' || isStreaming
                      "
                      @change="toggleApprovalArtifactType(msg, option.type, $event.target.checked)"
                    />
                    <span class="approval-selector-check" aria-hidden="true">
                      <Check class="approval-selector-check-icon" />
                    </span>
                    <span class="approval-selector-option-text">{{ option.label }}</span>
                  </label>
                </div>

                <div class="approval-actions">
                  <button
                    type="button"
                    class="approval-btn approval-btn-primary"
                    :disabled="isApprovalConfirmDisabled(msg, index)"
                    @click="confirmApproval(msg)"
                  >
                    {{ msg.approval?.confirm_label || '确认并继续' }}
                  </button>
                  <button
                    type="button"
                    class="approval-btn approval-btn-secondary"
                    :disabled="!isApprovalCardActionable(index) || msg.state === 'resolved' || isStreaming"
                    @click="cancelApproval(msg)"
                  >
                    {{ msg.approval?.cancel_label || '取消并修改' }}
                  </button>
                </div>
              </div>
            </template>

            <div v-if="msg.attachments && msg.attachments.length > 0" class="message-attachments">
              <div
                v-for="file in msg.attachments"
                :key="file.id || file.uid || file.name"
                class="attachment-card sent-attachment"
              >
                <FileText class="file-icon" />
                <span class="file-name" :title="file.name">{{ file.name }}</span>
              </div>
            </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <div class="chat-footer">
      <transition name="suggestion-fade">
        <div v-if="showSuggestions" class="suggestion-layer">
          <div class="suggestion-list">
            <button
              v-for="suggestion in activeSuggestions"
              :key="suggestion"
              type="button"
              class="suggestion-chip"
              @click="applySuggestion(suggestion)"
            >
              {{ suggestion }}
            </button>
          </div>
        </div>
      </transition>

      <div class="input-container" :class="{ 'has-files': pendingAttachments.length > 0 }">
        <div class="toolbar">
          <button class="tool-btn" title="添加资料" @click="triggerAttachmentUpload">
            <Paperclip class="tool-icon" />
            <span class="tool-text">资料</span>
          </button>
          <button
            class="tool-btn"
            :class="{
              'is-active': isVoiceRecording,
              'is-processing': isVoiceTranscribing
            }"
            :disabled="isVoiceTranscribing || (!isVoiceInputSupported && !isVoiceBusy)"
            :title="voiceButtonTitle"
            @click="toggleVoiceRecording"
          >
            <Loader2 v-if="isVoiceTranscribing" class="tool-icon spin-icon" />
            <Square v-else-if="isVoiceRecording" class="tool-icon" />
            <Mic v-else class="tool-icon" />
            <span class="tool-text">{{ voiceButtonText }}</span>
          </button>
          <button class="tool-btn" title="教案模板">
            <LayoutTemplate class="tool-icon" />
            <span class="tool-text">模板</span>
          </button>
          <input
            ref="attachmentInputRef"
            type="file"
            multiple
            accept=".docx,.pdf,.mp4"
            style="display: none"
            @change="handleAttachmentSelect"
          />
        </div>

        <div v-if="pendingAttachments.length > 0" class="attachments-preview">
          <div
            v-for="file in pendingAttachments"
            :key="file.uid"
            class="attachment-card"
            :class="{
              'is-processing': isPendingAttachmentProcessing(file),
              'is-error': file.status === 'error'
            }"
          >
            <div v-if="shouldShowPendingAttachmentSpinner(file)" class="uploading-spinner">
              <Loader2 class="spinner-icon" />
            </div>
            <FileText v-else class="file-icon" />

            <div class="attachment-meta">
              <span class="file-name" :title="file.name">{{ file.name }}</span>
              <span v-if="getPendingAttachmentStatusText(file)" class="attachment-status-text">
                {{ getPendingAttachmentStatusText(file) }}
              </span>
            </div>

            <button
              v-if="!isPendingAttachmentProcessing(file)"
              class="remove-file-btn"
              @click="removeAttachment(file.uid)"
            >
              <X class="remove-icon" />
            </button>
          </div>
        </div>

        <textarea
          ref="inputTextareaRef"
          v-model="inputText"
          class="chat-input"
          rows="3"
          placeholder="例如：请帮我为高一数学《函数》设计一节导入课。"
          @keydown.enter.prevent="sendMessage"
        ></textarea>

        <div class="send-action">
          <button
            class="send-btn"
            :disabled="!canSend"
            :class="{ 'is-disabled': !canSend }"
            title="发送 (Enter)"
            @click="sendMessage"
          >
            <Send class="send-icon" />
            <span>发送</span>
          </button>
        </div>
      </div>
      <div class="footer-hint">AI 生成内容仅供参考，请结合实际教学场景进行调整</div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  AlertCircle,
  Bot,
  ChevronDown,
  ChevronRight,
  Check,
  FileText,
  LayoutTemplate,
  Loader2,
  MessageSquarePlus,
  Mic,
  MessageSquareShare,
  MoreHorizontal,
  Paperclip,
  Send,
  Square,
  User,
  X
} from 'lucide-vue-next'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'

import {
  createChatRunAPI,
  getActiveChatRunAPI,
  getChatRunAPI,
  openChatRunEventStream
} from '@/api/chat'
import {
  getSseEventSequence,
  isTerminalRunStatus,
  parseSseEvent,
  shouldApplyRunEvent,
  shouldRetryRunStream,
  splitSseBlocks
} from '@/api/chatRunStream'
import { transcribeVoiceAttachmentAPI, uploadAttachmentFileAPI } from '@/api/file'
import { getMessageHistry } from '@/api/session'
import { useArtifactStore } from '@/store/artifact'
import { useSessionStore } from '@/store/session'
import AiMarkdownMessage from './AiMarkdownMessage.vue'
import { normalizeMarkdownSource as normalizeMessageContent } from './markdown'

const sessionStore = useSessionStore()
const artifactStore = useArtifactStore()
const { activeSessionId, activeThreadId: threadId, activePlanId } = storeToRefs(sessionStore)

const chatBodyRef = ref(null)
const attachmentInputRef = ref(null)
const inputTextareaRef = ref(null)

const messages = ref([])
const inputText = ref('')
const pendingAttachments = ref([])
const isStreaming = ref(false)
const recordingStreamRef = ref(null)
const audioContextRef = ref(null)
const recordingSourceNodeRef = ref(null)
const recordingProcessorNodeRef = ref(null)
const recordingGainNodeRef = ref(null)
const recordingChunksRef = ref([])
const recordingSampleRateRef = ref(44100)
const voiceStatus = ref('idle')
const voiceTranscriptTypewriterRunId = ref(0)
const isPinnedToBottom = ref(true)
const activeSuggestions = ref([])
const activeSuggestionRunId = ref('')
const skipSuggestionsForCurrentStream = ref(false)

const AUTO_SCROLL_THRESHOLD = 48
const VOICE_TRANSCRIPT_TYPE_INTERVAL_MS = 22
const RUN_RECONNECT_MAX_DELAY_MS = 8000
const showSuggestions = computed(() => {
  return activeSuggestions.value.length > 0 && !!activeSuggestionRunId.value
})

const isVoiceInputSupported =
  typeof window !== 'undefined' &&
  typeof navigator !== 'undefined' &&
  !!navigator.mediaDevices?.getUserMedia &&
  !!(window.AudioContext || window.webkitAudioContext)

const isVoiceRecording = computed(() => voiceStatus.value === 'recording')
const isVoiceTranscribing = computed(() => voiceStatus.value === 'transcribing')
const isVoiceBusy = computed(() => isVoiceRecording.value || isVoiceTranscribing.value)
const voiceButtonText = computed(() => {
  if (isVoiceTranscribing.value) {
    return '识别中'
  }
  if (isVoiceRecording.value) {
    return '停止'
  }
  return '语音'
})
const voiceButtonTitle = computed(() => {
  if (isVoiceTranscribing.value) {
    return '识别中'
  }
  if (isVoiceRecording.value) {
    return '停止录音'
  }
  return '语音输入'
})

const hasProcessingAttachments = computed(() =>
  pendingAttachments.value.some((file) => isPendingAttachmentProcessing(file))
)

const canSend = computed(() => {
  return (
    inputText.value.trim().length > 0 &&
    !isStreaming.value &&
    !hasProcessingAttachments.value &&
    !isVoiceBusy.value
  )
})

const approvalMetadataFields = [
  { key: 'subject', label: '学科' },
  { key: 'grade', label: '年级' },
  { key: 'topic', label: '主题' },
  { key: 'course_duration', label: '课时/时长' },
  { key: 'core_points', label: '核心内容' },
  { key: 'key_points', label: '重点' },
  { key: 'difficult_points', label: '难点' },
  { key: 'teaching_objectives', label: '教学目标' }
]

const approvalMetadataAliases = Object.freeze(
  approvalMetadataFields.reduce((result, field) => {
    result[field.key] = field.label
    return result
  }, {})
)

const approvalMetadataOrderedKeys = approvalMetadataFields.map((field) => field.key)
const approvalMetadataHiddenKeys = new Set(['is_complete'])
const defaultTeachingPlanArtifactOptions = Object.freeze([
  { type: 'ppt', label: '课件 PPT', selected: true },
  { type: 'docx', label: 'DOCX 教案', selected: true },
  { type: 'html-game', label: 'HTML 互动演示', selected: true }
])

const createAttachmentUid = () => {
  return `${Date.now()}_${Math.random().toString(16).slice(2)}`
}

const isNearBottom = (element) => {
  if (!element) {
    return true
  }

  return element.scrollHeight - element.scrollTop - element.clientHeight <= AUTO_SCROLL_THRESHOLD
}

const handleChatScroll = () => {
  isPinnedToBottom.value = isNearBottom(chatBodyRef.value)
}

const handleAiMessageRendered = async () => {
  await scrollToBottom()
}

const createPendingAttachment = (file) => {
  return {
    uid: createAttachmentUid(),
    kind: 'document',
    id: null,
    name: file.name,
    size: file.size,
    status: 'uploading',
    errorMessage: '',
    transcript: ''
  }
}

const createStreamState = (sessionId, runId = '', runThreadId = '', lastEventSequence = 0) => {
  return {
    sessionId,
    threadId: runThreadId,
    runId,
    lastEventSequence,
    progressMessageIndex: -1,
    aiMessageIndex: -1,
    hasReceivedToken: false,
    hasReceivedError: false,
    terminalStatus: ''
  }
}

const COMPRESSED_CONTEXT_MARKER = '[SmartClass compressed thread context]'

const artifactTypeLabels = Object.freeze({
  ppt: '课件 PPT',
  docx: 'DOCX 教案',
  'html-game': 'HTML 互动演示'
})

const normalizeArtifactTraceText = (value) => {
  if (typeof value !== 'string') {
    return ''
  }
  return value.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim()
}

const isArtifactTraceEntryExpandedByDefault = (kind = 'status') => {
  if (kind === 'tool_call' || kind === 'tool_result') {
    return false
  }
  return true
}

const createArtifactTraceEntry = (entry = {}) => {
  return {
    entryId: entry?.entry_id || `${Date.now()}_${Math.random().toString(16).slice(2)}`,
    kind: entry?.kind || 'status',
    title: entry?.title || '',
    content: normalizeArtifactTraceText(entry?.content || ''),
    status: entry?.status || '',
    expanded:
      typeof entry?.expanded === 'boolean'
        ? entry.expanded
        : isArtifactTraceEntryExpandedByDefault(entry?.kind)
  }
}

const createArtifactTraceCard = (payload = {}) => {
  const initialEntry = createArtifactTraceEntry(payload.entry || {})
  return {
    artifactRunId: payload?.artifact_run_id || '',
    artifactType: payload?.artifact_type || '',
    artifactTitle: payload?.artifact_title || '',
    mode: payload?.mode || 'create',
    status: initialEntry.status || 'running',
    entries: [initialEntry]
  }
}

const isActiveStreamState = (streamState) => {
  return (
    !!streamState &&
    streamState.sessionId === activeSessionId.value &&
    streamState.threadId === threadId.value
  )
}

const clearSuggestions = () => {
  activeSuggestions.value = []
  activeSuggestionRunId.value = ''
}

const normalizeApprovalArtifactOptions = (approval = {}) => {
  if (approval?.stage !== 'teaching_plan_review') {
    return []
  }

  const rawOptions =
    Array.isArray(approval?.artifact_options) && approval.artifact_options.length > 0
      ? approval.artifact_options
      : defaultTeachingPlanArtifactOptions

  return rawOptions.map((option) => ({
    type: option?.type,
    label: option?.label || option?.type || '',
    selected: option?.selected !== false
  }))
}

const normalizeApprovalMessage = (message = {}) => {
  const approval = message?.approval || {}
  const normalizedOptions = normalizeApprovalArtifactOptions(approval)
  const selectedArtifactTypes = normalizedOptions
    .filter((option) => option.selected)
    .map((option) => option.type)

  return {
    ...message,
    role: 'ai',
    type: 'approval-card',
    state: message?.state || 'pending',
    approval: {
      ...approval,
      artifact_options: normalizedOptions.length > 0 ? normalizedOptions : approval?.artifact_options || []
    },
    selectedArtifactTypes
  }
}

const findLatestApprovalCardIndex = () => {
  for (let index = messages.value.length - 1; index >= 0; index -= 1) {
    if (messages.value[index]?.type === 'approval-card') {
      return index
    }
  }
  return -1
}

const isApprovalCardActionable = (index) => {
  if (index < 0 || index >= messages.value.length) {
    return false
  }
  return index === findLatestApprovalCardIndex()
}

const getApprovalArtifactOptions = (message) => {
  return Array.isArray(message?.approval?.artifact_options) ? message.approval.artifact_options : []
}

const isArtifactOptionSelected = (message, artifactType) => {
  return Array.isArray(message?.selectedArtifactTypes)
    ? message.selectedArtifactTypes.includes(artifactType)
    : false
}

const isApprovalSelectionEmpty = (message) => {
  return message?.approval?.stage === 'teaching_plan_review' && !(message?.selectedArtifactTypes?.length > 0)
}

const isApprovalConfirmDisabled = (message, index) => {
  if (!isApprovalCardActionable(index) || message?.state === 'resolved' || isStreaming.value) {
    return true
  }
  return isApprovalSelectionEmpty(message)
}

const toggleApprovalArtifactType = (message, artifactType, checked) => {
  if (!message || message?.approval?.stage !== 'teaching_plan_review') {
    return
  }

  const current = Array.isArray(message.selectedArtifactTypes) ? [...message.selectedArtifactTypes] : []
  const next = checked
    ? [...new Set([...current, artifactType])]
    : current.filter((item) => item !== artifactType)
  message.selectedArtifactTypes = next
}

const markApprovalCardsResolved = () => {
  messages.value.forEach((message) => {
    if (message?.type === 'approval-card' && message.state !== 'resolved') {
      message.state = 'resolved'
    }
  })
}

const focusChatInput = async () => {
  await nextTick()
  inputTextareaRef.value?.focus?.()
}

const getApprovalTitle = (message) => {
  return message?.approval?.title || '请确认当前流程'
}

const getApprovalDescription = (message) => {
  if (message?.state === 'awaiting-feedback') {
    return '流程保持暂停，等待你补充修改意见。'
  }
  return message?.approval?.description || ''
}

const formatApprovalMetadataKey = (key) => {
  if (!key) {
    return 'Metadata'
  }

  if (approvalMetadataAliases[key]) {
    return approvalMetadataAliases[key]
  }

  const normalizedKey = String(key)
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  if (!normalizedKey) {
    return String(key)
  }

  return normalizedKey.replace(/\b\w/g, (char) => char.toUpperCase())
}

const getApprovalMetadataEntries = (message) => {
  const metadata = message?.approval?.metadata
  if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) {
    return []
  }

  const entries = []
  const seenKeys = new Set()

  approvalMetadataOrderedKeys.forEach((key) => {
    if (!(key in metadata) || approvalMetadataHiddenKeys.has(key)) {
      return
    }
    seenKeys.add(key)
    entries.push({
      key,
      label: formatApprovalMetadataKey(key),
      value: metadata[key]
    })
  })

  Object.entries(metadata).forEach(([key, value]) => {
    if (seenKeys.has(key) || approvalMetadataHiddenKeys.has(key)) {
      return
    }
    entries.push({
      key,
      label: formatApprovalMetadataKey(key),
      value
    })
  })

  return entries
}

const formatApprovalMetadataValue = (value) => {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join('、') : '未提供'
  }
  if (value === null || value === undefined) {
    return '未提供'
  }
  const text = String(value).trim()
  return text ? text : '未提供'
}

const formatDynamicApprovalMetadataValue = (value) => {
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return '未提供'
    }

    const allPrimitiveValues = value.every(
      (item) =>
        item === null ||
        item === undefined ||
        ['string', 'number', 'boolean'].includes(typeof item)
    )
    if (allPrimitiveValues) {
      return value
        .map((item) => {
          if (item === null || item === undefined) {
            return '未提供'
          }
          const normalizedItem = String(item).trim()
          return normalizedItem || '未提供'
        })
        .join('、')
    }

    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }

  if (value === null || value === undefined) {
    return '未提供'
  }

  if (typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }

  const text = String(value).trim()
  return text || '未提供'
}

const upsertApprovalCard = async (payload) => {
  if (!payload?.interrupt_id) {
    return
  }

  clearSuggestions()
  const normalizedMessage = normalizeApprovalMessage({
    role: 'ai',
    type: 'approval-card',
    runId: payload.run_id || '',
    approval: payload,
    state: 'pending'
  })

  const existingIndex = messages.value.findIndex(
    (message) =>
      message?.type === 'approval-card' &&
      message?.approval?.interrupt_id === payload.interrupt_id
  )

  if (existingIndex >= 0) {
    messages.value[existingIndex] = {
      ...messages.value[existingIndex],
      ...normalizedMessage
    }
  } else {
    markApprovalCardsResolved()
    messages.value.push(normalizedMessage)
  }

  await scrollToBottom()
}

const normalizeSuggestions = (items = []) => {
  if (!Array.isArray(items)) {
    return []
  }

  const normalized = []
  const seen = new Set()

  items.forEach((item) => {
    const text = normalizeMessageContent(item).trim()
    if (!text) {
      return
    }

    const dedupeKey = text.toLocaleLowerCase()
    if (seen.has(dedupeKey)) {
      return
    }

    seen.add(dedupeKey)
    normalized.push(text)
  })

  return normalized.slice(0, 3)
}

const focusInput = async () => {
  await nextTick()
  inputTextareaRef.value?.focus()
}

const applySuggestion = async (suggestion) => {
  inputText.value = suggestion
  clearSuggestions()
  await focusInput()
}

const updatePendingAttachment = (uid, patch) => {
  const target = pendingAttachments.value.find((file) => file.uid === uid)
  if (!target) {
    return
  }
  Object.assign(target, patch)
}

const removePendingAttachmentByUid = (uid) => {
  const index = pendingAttachments.value.findIndex((file) => file.uid === uid)
  if (index > -1) {
    pendingAttachments.value.splice(index, 1)
  }
}

const isPendingAttachmentProcessing = (file) => {
  return ['uploading', 'transcribing'].includes(file?.status)
}

const shouldShowPendingAttachmentSpinner = (file) => {
  return ['uploading', 'transcribing'].includes(file?.status)
}

const getPendingAttachmentStatusText = (file) => {
  if (!file) {
    return ''
  }
  if (file.status === 'uploading') {
    return '上传中...'
  }
  if (file.status === 'error') {
    return file.errorMessage || '上传失败'
  }
  return ''
}

const getSuccessfulAttachments = () => {
  return pendingAttachments.value
    .filter((file) => file.kind === 'document' && file.status === 'ready' && file.id)
    .map((file) => ({
      uid: file.uid,
      id: file.id,
      name: file.name,
      size: file.size
    }))
}

const ensureComposerContext = () => {
  if (!activePlanId.value) {
    ElMessage.warning('请先选择或新建一个左侧的教学计划')
    return false
  }
  if (!threadId.value) {
    ElMessage.warning('请先选择一个会话后再上传附件')
    return false
  }
  return true
}

const triggerAttachmentUpload = () => {
  if (!ensureComposerContext()) {
    return
  }
  attachmentInputRef.value?.click()
}

const buildVoiceAttachmentName = () => {
  const now = new Date()
  const parts = [now.getHours(), now.getMinutes(), now.getSeconds()].map((value) =>
    String(value).padStart(2, '0')
  )
  return `voice_${parts.join('')}.wav`
}

const cancelVoiceTranscriptTypewriter = () => {
  voiceTranscriptTypewriterRunId.value += 1
}

const appendTranscriptToInput = async (transcript) => {
  if (!transcript) {
    return
  }

  cancelVoiceTranscriptTypewriter()
  const runId = voiceTranscriptTypewriterRunId.value
  const prefix = inputText.value.trim().length > 0 ? `${inputText.value.trimEnd()}\n` : ''
  inputText.value = prefix
  await focusInput()

  for (const char of transcript) {
    if (runId !== voiceTranscriptTypewriterRunId.value) {
      return
    }
    inputText.value += char
    await new Promise((resolve) => window.setTimeout(resolve, VOICE_TRANSCRIPT_TYPE_INTERVAL_MS))
  }
}

const mergeRecordingSamples = (chunks) => {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
  const merged = new Float32Array(totalLength)
  let offset = 0

  chunks.forEach((chunk) => {
    merged.set(chunk, offset)
    offset += chunk.length
  })

  return merged
}

const encodeWavBlob = (samples, sampleRate) => {
  const bytesPerSample = 2
  const buffer = new ArrayBuffer(44 + samples.length * bytesPerSample)
  const view = new DataView(buffer)

  const writeAscii = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index))
    }
  }

  writeAscii(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * bytesPerSample, true)
  writeAscii(8, 'WAVE')
  writeAscii(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * bytesPerSample, true)
  view.setUint16(32, bytesPerSample, true)
  view.setUint16(34, 16, true)
  writeAscii(36, 'data')
  view.setUint32(40, samples.length * bytesPerSample, true)

  let offset = 44
  samples.forEach((sample) => {
    const normalized = Math.max(-1, Math.min(1, sample))
    const pcm = normalized < 0 ? normalized * 0x8000 : normalized * 0x7fff
    view.setInt16(offset, pcm, true)
    offset += bytesPerSample
  })

  return new Blob([buffer], { type: 'audio/wav' })
}

const cleanupVoiceRecorder = () => {
  recordingChunksRef.value = []
  recordingSampleRateRef.value = 44100

  if (recordingProcessorNodeRef.value) {
    recordingProcessorNodeRef.value.onaudioprocess = null
    recordingProcessorNodeRef.value.disconnect()
  }
  if (recordingSourceNodeRef.value) {
    recordingSourceNodeRef.value.disconnect()
  }
  if (recordingGainNodeRef.value) {
    recordingGainNodeRef.value.disconnect()
  }
  if (recordingStreamRef.value) {
    recordingStreamRef.value.getTracks().forEach((track) => track.stop())
  }
  if (audioContextRef.value) {
    Promise.resolve(audioContextRef.value.close()).catch(() => {})
  }

  recordingStreamRef.value = null
  audioContextRef.value = null
  recordingSourceNodeRef.value = null
  recordingProcessorNodeRef.value = null
  recordingGainNodeRef.value = null
}

const discardVoiceRecording = () => {
  cleanupVoiceRecorder()
  voiceStatus.value = 'idle'
}

const finalizeVoiceRecording = async () => {
  const sessionIdAtStart = activeSessionId.value
  const mergedSamples = mergeRecordingSamples(recordingChunksRef.value)
  const sampleRate = recordingSampleRateRef.value
  cleanupVoiceRecorder()
  voiceStatus.value = 'transcribing'

  if (!mergedSamples.length) {
    voiceStatus.value = 'idle'
    ElMessage.error('录音内容为空')
    return
  }

  const voiceBlob = encodeWavBlob(mergedSamples, sampleRate)
  const voiceFile = new File([voiceBlob], buildVoiceAttachmentName(), {
    type: 'audio/wav'
  })
  await transcribeVoiceAttachment(voiceFile, sessionIdAtStart)
}

const transcribeVoiceAttachment = async (voiceFile, sessionIdAtStart) => {
  try {
    const res = await transcribeVoiceAttachmentAPI(activePlanId.value, threadId.value, voiceFile)
    const payload = res?.data || res
    const transcript = normalizeMessageContent(payload?.transcript || '').trim()

    if (transcript && sessionIdAtStart === activeSessionId.value) {
      await appendTranscriptToInput(transcript)
    }
  } catch (error) {
    const errorMessage =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      '语音转写失败'
    ElMessage.error(errorMessage)
  } finally {
    voiceStatus.value = 'idle'
  }
}

const toggleVoiceRecording = async () => {
  if (isVoiceTranscribing.value) {
    return
  }
  if (isVoiceRecording.value) {
    await finalizeVoiceRecording()
    return
  }
  if (!isVoiceInputSupported) {
    ElMessage.warning('当前浏览器不支持语音输入，请使用桌面版 Chrome 或 Edge。')
    return
  }
  if (!ensureComposerContext()) {
    return
  }

  try {
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const audioContext = new AudioContextCtor()
    const sourceNode = audioContext.createMediaStreamSource(stream)
    const processorNode = audioContext.createScriptProcessor(4096, 1, 1)
    const gainNode = audioContext.createGain()
    gainNode.gain.value = 0

    recordingStreamRef.value = stream
    audioContextRef.value = audioContext
    recordingSourceNodeRef.value = sourceNode
    recordingProcessorNodeRef.value = processorNode
    recordingGainNodeRef.value = gainNode
    recordingChunksRef.value = []
    recordingSampleRateRef.value = audioContext.sampleRate
    voiceStatus.value = 'recording'

    processorNode.onaudioprocess = (event) => {
      const inputData = event.inputBuffer.getChannelData(0)
      recordingChunksRef.value.push(new Float32Array(inputData))
    }

    sourceNode.connect(processorNode)
    processorNode.connect(gainNode)
    gainNode.connect(audioContext.destination)
    await audioContext.resume()
    await scrollToBottom()
  } catch (error) {
    const errorMessage =
      error?.name === 'NotAllowedError'
        ? '麦克风权限被拒绝，请允许浏览器访问麦克风。'
        : '无法启动录音，请稍后重试。'
    cleanupVoiceRecorder()
    voiceStatus.value = 'idle'
    ElMessage.error(errorMessage)
  }
}

const uploadAttachment = async (rawFile) => {
  const localAttachment = createPendingAttachment(rawFile)
  pendingAttachments.value.push(localAttachment)
  await scrollToBottom()

  try {
    const res = await uploadAttachmentFileAPI(activePlanId.value, threadId.value, rawFile)
    const attachment = res?.data || res

    updatePendingAttachment(localAttachment.uid, {
      id: attachment?.id ?? null,
      status: 'ready',
      errorMessage: ''
    })
  } catch (error) {
    const errorMessage =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      '上传失败'

    updatePendingAttachment(localAttachment.uid, {
      status: 'error',
      errorMessage
    })
    ElMessage.error(`${rawFile.name} 上传失败`)
  } finally {
    await scrollToBottom()
  }
}

const handleAttachmentSelect = async (event) => {
  const files = Array.from(event.target.files || [])
  event.target.value = ''

  if (!files.length) {
    return
  }
  if (!ensureComposerContext()) {
    return
  }

  files.forEach((file) => {
    uploadAttachment(file)
  })
}

const removeAttachment = (uid) => {
  removePendingAttachmentByUid(uid)
}

const appendErrorMessage = async (content = '对话请求失败，请稍后重试。') => {
  messages.value.push({
    role: 'ai',
    type: 'text',
    content: normalizeMessageContent(content)
  })
  await scrollToBottom()
}

const parseJsonPayload = (value) => {
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

const ensureProgressMessage = (streamState, runId) => {
  const current = messages.value[streamState.progressMessageIndex]
  if (current?.type === 'progress-status' && current.runId === runId) {
    return current
  }

  messages.value.push({
    role: 'ai',
    type: 'progress-status',
    runId,
    steps: [],
    isComplete: false
  })
  streamState.progressMessageIndex = messages.value.length - 1
  return messages.value[streamState.progressMessageIndex]
}

const ensureAiTextMessage = (streamState, runId = '') => {
  const current = messages.value[streamState.aiMessageIndex]
  if (current?.type === 'text' && current.role === 'ai' && current.runId === runId) {
    return current
  }

  messages.value.push({
    role: 'ai',
    type: 'text',
    runId,
    content: '',
    isPending: false
  })
  streamState.aiMessageIndex = messages.value.length - 1
  return messages.value[streamState.aiMessageIndex]
}

const findArtifactTraceGroupIndex = (runId = '') => {
  if (!runId) {
    return -1
  }
  for (let index = messages.value.length - 1; index >= 0; index -= 1) {
    const message = messages.value[index]
    if (message?.type === 'artifact-trace-group' && message?.runId === runId) {
      return index
    }
  }
  return -1
}

const ensureArtifactTraceGroupMessage = (runId = '') => {
  const existingIndex = findArtifactTraceGroupIndex(runId)
  if (existingIndex >= 0) {
    return messages.value[existingIndex]
  }

  const message = {
    role: 'ai',
    type: 'artifact-trace-group',
    runId,
    cards: []
  }
  messages.value.push(message)
  return message
}

const upsertArtifactTraceEntry = async (streamState, payload) => {
  if (!isActiveStreamState(streamState) || !payload?.run_id || !payload?.artifact_run_id || !payload?.entry) {
    return
  }

  const group = ensureArtifactTraceGroupMessage(payload.run_id)
  const entry = createArtifactTraceEntry(payload.entry)
  let card = Array.isArray(group.cards)
    ? group.cards.find((item) => item?.artifactRunId === payload.artifact_run_id)
    : null

  if (!card) {
    if (!Array.isArray(group.cards)) {
      group.cards = []
    }
    card = createArtifactTraceCard(payload)
    group.cards.push(card)
  } else {
    const existingEntryIndex = card.entries.findIndex((item) => item.entryId === entry.entryId)
    if (existingEntryIndex >= 0) {
      const previousEntry = card.entries[existingEntryIndex]
      card.entries[existingEntryIndex] = {
        ...previousEntry,
        ...entry,
        expanded:
          typeof previousEntry?.expanded === 'boolean'
            ? previousEntry.expanded
            : entry.expanded
      }
    } else {
      card.entries.push(entry)
    }
    card.artifactType = payload?.artifact_type || card.artifactType
    card.artifactTitle = payload?.artifact_title || card.artifactTitle
    card.mode = payload?.mode || card.mode
  }

  if (entry.status) {
    card.status = entry.status
  }

  await scrollToBottom()
}

const getArtifactTraceCardTitle = (card = {}) => {
  return card?.artifactTitle || artifactTypeLabels[card?.artifactType] || '产物'
}

const getArtifactTraceModeLabel = (mode = 'create') => {
  return mode === 'revise' ? '差量修改过程' : '生成过程'
}

const getArtifactTraceStatusLabel = (card = {}) => {
  if (card?.status === 'success') {
    return card?.mode === 'revise' ? '修改完成' : '生成完成'
  }
  if (card?.status === 'failed') {
    return card?.mode === 'revise' ? '修改失败' : '生成失败'
  }
  return card?.mode === 'revise' ? '修改中' : '生成中'
}

const getArtifactTraceEntryKindLabel = (kind = 'status') => {
  if (kind === 'tool_call') {
    return '工具调用'
  }
  if (kind === 'tool_result') {
    return '工具结果'
  }
  if (kind === 'ai_message') {
    return 'AI 输出'
  }
  return '状态更新'
}

const canToggleArtifactTraceEntry = (entry = {}) => {
  return Boolean(entry?.content)
}

const isArtifactTraceEntryExpanded = (entry = {}) => {
  if (!canToggleArtifactTraceEntry(entry)) {
    return true
  }
  return entry?.expanded !== false
}

const toggleArtifactTraceEntry = (entry) => {
  if (!canToggleArtifactTraceEntry(entry)) {
    return
  }
  entry.expanded = !isArtifactTraceEntryExpanded(entry)
}

const getArtifactTraceToggleLabel = (entry = {}) => {
  return isArtifactTraceEntryExpanded(entry) ? '收起' : '展开'
}

const shouldRenderMessage = (message) => {
  if (!message) {
    return false
  }
  if (message.isContextCompressed || normalizeMessageContent(message.content || '').startsWith(COMPRESSED_CONTEXT_MARKER)) {
    return false
  }

  if (message.type && message.type !== 'text') {
    return true
  }

  const hasAttachments = Array.isArray(message.attachments) && message.attachments.length > 0
  const content = normalizeMessageContent(message.content || '').trim()
  return Boolean(content || message.isPending || hasAttachments)
}

const removeEmptyAiPlaceholderMessage = (streamState, runId = '') => {
  const currentIndex = streamState.aiMessageIndex
  if (currentIndex < 0) {
    return
  }

  const current = messages.value[currentIndex]
  const isMatchingAiMessage =
    current?.type === 'text' && current.role === 'ai' && current.runId === runId
  if (!isMatchingAiMessage) {
    return
  }

  const hasContent = normalizeMessageContent(current.content || '').trim().length > 0
  if (current.isPending || hasContent) {
    return
  }

  messages.value.splice(currentIndex, 1)
  streamState.aiMessageIndex = -1
}

const shouldShowPendingAiMessage = (steps = []) => {
  return steps.length > 0 && steps.every((step) => step.status === 'success')
}

const updateProgressMessage = async (streamState, payload) => {
  if (!isActiveStreamState(streamState) || !payload?.run_id) {
    return
  }

  const message = ensureProgressMessage(streamState, payload.run_id)
  message.steps = Array.isArray(payload.steps) ? payload.steps : []
  message.isComplete =
    message.steps.length > 0 &&
    message.steps.every((step) => ['success', 'failed'].includes(step.status))

  if (!streamState.hasReceivedToken && !streamState.hasReceivedError) {
    const shouldPending = shouldShowPendingAiMessage(message.steps)
    const currentAiMessage = messages.value[streamState.aiMessageIndex]
    const hasCurrentAiMessage =
      currentAiMessage?.type === 'text' &&
      currentAiMessage.role === 'ai' &&
      currentAiMessage.runId === payload.run_id

    if (shouldPending || hasCurrentAiMessage) {
      if (shouldPending) {
        const aiMessage = ensureAiTextMessage(streamState, payload.run_id)
        aiMessage.isPending = true
      } else if (hasCurrentAiMessage) {
        currentAiMessage.isPending = false
        removeEmptyAiPlaceholderMessage(streamState, payload.run_id)
      }
    }
  }

  await scrollToBottom()
}

const appendTokenToMessage = async (streamState, runId, text) => {
  if (!text || !isActiveStreamState(streamState)) {
    return
  }

  const aiMessage = ensureAiTextMessage(streamState, runId)
  aiMessage.isPending = false
  aiMessage.content = `${normalizeMessageContent(aiMessage.content)}${text}`
}

const markProgressFailed = async (streamState, stepKey, detail) => {
  const message = messages.value[streamState.progressMessageIndex]
  if (!message || message.type !== 'progress-status') {
    return
  }

  let targetStep = null
  if (stepKey) {
    targetStep = message.steps.find((step) => step.step_key === stepKey)
  }
  if (!targetStep) {
    targetStep = [...message.steps].reverse().find((step) => step.status === 'running')
  }

  if (targetStep) {
    targetStep.status = 'failed'
    if (detail) {
      targetStep.detail = detail
    }
  }
  message.isComplete =
    message.steps.length > 0 &&
    message.steps.every((step) => ['success', 'failed'].includes(step.status))

  await scrollToBottom()
}

const updateSuggestions = (streamState, payload) => {
  if (!isActiveStreamState(streamState) || !payload?.run_id) {
    return
  }
  if (streamState.runId && payload.run_id !== streamState.runId) {
    return
  }
  if (!streamState.hasReceivedToken || streamState.hasReceivedError) {
    return
  }
  if (skipSuggestionsForCurrentStream.value || inputText.value.trim().length > 0) {
    return
  }

  const suggestions = normalizeSuggestions(payload.suggestions)
  if (!suggestions.length) {
    return
  }

  activeSuggestionRunId.value = payload.run_id
  activeSuggestions.value = suggestions
}

const handleParsedEvent = async (event, data, streamState) => {
  if (event === 'done' || data === '[DONE]') {
    const payload = parseJsonPayload(data)
    streamState.terminalStatus = payload?.status || streamState.terminalStatus || 'succeeded'
    sessionStore.updateChatRunStatus(streamState.threadId, streamState.runId, streamState.terminalStatus)
    if (isActiveStreamState(streamState)) {
      const progressMessage = messages.value[streamState.progressMessageIndex]
      if (progressMessage?.type === 'progress-status') {
        progressMessage.isComplete =
          progressMessage.steps.length > 0 &&
          progressMessage.steps.every((step) => ['success', 'failed'].includes(step.status))
      }
    }
    return true
  }

  if (!isActiveStreamState(streamState) && event !== 'done') {
    return false
  }

  if (event === 'metadata') {
    const payload = parseJsonPayload(data)
    if (payload?.thread_id) {
      threadId.value = payload.thread_id
    }
    if (payload?.run_id) {
      streamState.runId = payload.run_id
    }
    return false
  }

  if (event === 'progress') {
    const payload = parseJsonPayload(data)
    if (payload?.run_id) {
      streamState.runId = payload.run_id
    }
    await updateProgressMessage(streamState, payload)
    return false
  }

  if (event === 'token') {
    const payload = parseJsonPayload(data)
    const text = payload?.text || ''
    if (text) {
      streamState.hasReceivedToken = true
      await appendTokenToMessage(streamState, payload?.run_id || streamState.runId, text)
    }
    return false
  }
  if (event === 'suggestions') {
    const payload = parseJsonPayload(data)
    updateSuggestions(streamState, payload)
    return false
  }

  if (event === 'artifact') {
    const payload = parseJsonPayload(data)
    if (payload?.artifact) {
      artifactStore.upsertArtifact(payload.artifact)
    }
    return false
  }

  if (event === 'artifact_trace') {
    const payload = parseJsonPayload(data)
    if (payload?.run_id) {
      streamState.runId = payload.run_id
    }
    await upsertArtifactTraceEntry(streamState, payload)
    return false
  }

  if (event === 'approval') {
    const payload = parseJsonPayload(data)
    if (payload?.run_id) {
      streamState.runId = payload.run_id
    }
    await upsertApprovalCard(payload)
    return false
  }

  if (event === 'error') {
    const payload = parseJsonPayload(data)
    streamState.hasReceivedError = true
    await markProgressFailed(streamState, payload?.step_key, payload?.message)
    await appendErrorMessage(payload?.message || '对话请求失败，请稍后重试。')
    return false
  }

  return false
}

const handleStreamResponse = async (response, streamState) => {
  if (!response.ok) {
    let message = `HTTP ${response.status}`
    try {
      const payload = await response.json()
      message = payload?.detail || payload?.message || message
    } catch {
      try {
        const text = await response.text()
        if (text) {
          message = text
        }
      } catch {
        // noop
      }
    }
    const requestError = new Error(message)
    requestError.status = response.status
    throw requestError
  }

  if (!response.body) {
    throw new Error('Empty response body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })

    const { eventBlocks, rest } = splitSseBlocks(buffer)
    buffer = rest

    for (const block of eventBlocks) {
      if (!block.trim()) continue

      const { id, event, data } = parseSseEvent(block)
      const sequence = getSseEventSequence(id)
      if (!shouldApplyRunEvent(streamState.lastEventSequence, sequence)) {
        continue
      }
      const shouldStop = await handleParsedEvent(event, data, streamState)
      if (sequence !== null) {
        streamState.lastEventSequence = sequence
        sessionStore.updateChatRunCursor(streamState.threadId, streamState.runId, sequence)
      }
      if (shouldStop) {
        return true
      }
    }

    if (done) {
      if (buffer.trim()) {
        const { id, event, data } = parseSseEvent(buffer)
        const sequence = getSseEventSequence(id)
        if (sequence !== null && shouldApplyRunEvent(streamState.lastEventSequence, sequence)) {
          const shouldStop = await handleParsedEvent(event, data, streamState)
          streamState.lastEventSequence = sequence
          sessionStore.updateChatRunCursor(streamState.threadId, streamState.runId, sequence)
          if (shouldStop) {
            return true
          }
        }
      }
      return false
    }
  }
}

const restoreRunOutputSnapshot = (streamState, run = {}) => {
  const outputText = normalizeMessageContent(run?.output_text || '')
  if (!outputText || !isActiveStreamState(streamState)) {
    return
  }
  const aiMessage = ensureAiTextMessage(streamState, run.run_id)
  aiMessage.content = outputText
  aiMessage.isPending = false
  streamState.hasReceivedToken = true
}

const waitForRunReconnect = (attempt) => {
  const delay = Math.min(500 * 2 ** Math.max(attempt, 0), RUN_RECONNECT_MAX_DELAY_MS)
  return new Promise((resolve) => window.setTimeout(resolve, delay))
}

const followChatRun = async (streamState) => {
  let reconnectAttempt = 0

  while (isActiveStreamState(streamState)) {
    const controller = new AbortController()
    sessionStore.setChatRunSubscription(streamState.threadId, controller)
    try {
      const response = await openChatRunEventStream(streamState.runId, streamState.lastEventSequence, {
        signal: controller.signal
      })
      const reachedTerminalEvent = await handleStreamResponse(response, streamState)
      reconnectAttempt = 0
      if (reachedTerminalEvent) {
        if (isActiveStreamState(streamState)) {
          isStreaming.value = false
          await artifactStore.fetchArtifacts(streamState.threadId).catch(() => [])
        }
        return true
      }

      const run = await getChatRunAPI(streamState.runId)
      sessionStore.setChatRunSnapshot(streamState.threadId, run)
      if (isTerminalRunStatus(run?.status)) {
        streamState.terminalStatus = run.status
        if (isActiveStreamState(streamState)) {
          isStreaming.value = false
        }
        return true
      }
    } catch (error) {
      if (error?.name === 'AbortError' || !isActiveStreamState(streamState)) {
        return false
      }
      if (!shouldRetryRunStream(error?.status)) {
        console.error('Chat run subscription stopped:', error)
        if (isActiveStreamState(streamState) && !streamState.hasReceivedError) {
          await appendErrorMessage(error?.message || '无法继续接收本轮对话。')
          isStreaming.value = false
        }
        return false
      }
      console.warn('Chat run subscription interrupted, retrying:', error)
    }

    await waitForRunReconnect(reconnectAttempt)
    reconnectAttempt += 1
  }
  return false
}

const requestStreamReply = async (content = '', attachmentIds = [], approval = null) => {
  const sessionIdAtStart = activeSessionId.value
  const threadIdAtStart = threadId.value
  isStreaming.value = true
  skipSuggestionsForCurrentStream.value = false

  const payload = { thread_id: threadIdAtStart || undefined }
  if (content) {
    payload.message = content
  }
  if (attachmentIds.length > 0) {
    payload.attachment_ids = attachmentIds
  }
  if (approval) {
    payload.approval = approval
  }

  let run = null
  try {
    run = await createChatRunAPI(payload)
  } catch (error) {
    const conflictRun = error?.response?.status === 409 ? error?.response?.data?.detail?.run : null
    if (conflictRun) {
      run = conflictRun
    } else {
      if (sessionIdAtStart === activeSessionId.value) {
        isStreaming.value = false
        const detail = error?.response?.data?.detail
        const errorMessage =
          (typeof detail === 'string' ? detail : detail?.message) ||
          error?.message ||
          '对话请求失败，请稍后重试。'
        await appendErrorMessage(errorMessage)
      }
      return false
    }
  }

  sessionStore.setChatRunSnapshot(threadIdAtStart, run)
  const streamState = createStreamState(
    sessionIdAtStart,
    run.run_id,
    threadIdAtStart,
    run.last_event_sequence || 0
  )
  restoreRunOutputSnapshot(streamState, run)
  await followChatRun(streamState)
  if (isActiveStreamState(streamState) && !isTerminalRunStatus(streamState.terminalStatus)) {
    const storedState = sessionStore.getChatRunState(threadIdAtStart)
    isStreaming.value = ['queued', 'running'].includes(storedState?.status)
  }
  await scrollToBottom()
  return true
}

const cancelApproval = async (message) => {
  if (!message || isStreaming.value) {
    return
  }
  message.state = 'awaiting-feedback'
  clearSuggestions()
  await focusChatInput()
}

const confirmApproval = async (message) => {
  const interruptId = message?.approval?.interrupt_id
  if (!interruptId || isStreaming.value) {
    return
  }
  if (isApprovalSelectionEmpty(message)) {
    ElMessage.warning('至少选择一个产物')
    return
  }

  const previousState = message.state
  clearSuggestions()
  markApprovalCardsResolved()
  message.state = 'resolved'

  const approvalPayload = {
    action: 'approve',
    interrupt_id: interruptId
  }
  if (message?.approval?.stage === 'teaching_plan_review') {
    approvalPayload.selected_artifact_types = [...(message.selectedArtifactTypes || [])]
  }

  const succeeded = await requestStreamReply('', [], approvalPayload)

  if (!succeeded) {
    message.state = previousState || 'pending'
  }
}

const sendMessage = async () => {
  if (!canSend.value) return

  const content = inputText.value.trim()
  const successfulAttachments = getSuccessfulAttachments()
  const attachmentIds = successfulAttachments.map((file) => file.id)

  clearSuggestions()
  markApprovalCardsResolved()

  messages.value.push({
    role: 'teacher',
    type: 'text',
    content: normalizeMessageContent(content),
    attachments: successfulAttachments.length > 0 ? successfulAttachments : undefined
  })

  inputText.value = ''
  pendingAttachments.value = []

  await scrollToBottom(true)
  await requestStreamReply(content, attachmentIds)
}

const scrollToBottom = async (force = false) => {
  await nextTick()
  if (!chatBodyRef.value) {
    return
  }

  if (!force && !isPinnedToBottom.value) {
    return
  }

  chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
  isPinnedToBottom.value = true
}

const normalizeMessageList = (items = []) => {
  if (!Array.isArray(items)) {
    return []
  }

  return items
    .filter((message) => {
      return !(
        message?.isContextCompressed ||
        normalizeMessageContent(message?.content || '').startsWith(COMPRESSED_CONTEXT_MARKER)
      )
    })
    .map((message) => {
      if (message?.type === 'approval-card') {
        return normalizeApprovalMessage(message)
      }

      return {
        ...message,
        content: normalizeMessageContent(message?.content)
      }
    })
}

const loadHistory = async (
  sessionIdAtStart = activeSessionId.value,
  threadIdAtStart = threadId.value
) => {
  if (isVoiceRecording.value) {
    discardVoiceRecording()
  }
  pendingAttachments.value = []
  clearSuggestions()
  skipSuggestionsForCurrentStream.value = false

  if (!sessionIdAtStart) {
    if (sessionIdAtStart === activeSessionId.value) {
      messages.value = []
    }
    return
  }

  const targetId = threadIdAtStart || sessionIdAtStart
  if (!targetId) {
    messages.value = []
    return
  }

  try {
    const res = await getMessageHistry(targetId)
    if (sessionIdAtStart !== activeSessionId.value || threadIdAtStart !== threadId.value) {
      return
    }
    if (res.data && res.data.messages) {
      messages.value = normalizeMessageList(res.data.messages)
    } else {
      messages.value = []
    }
    await scrollToBottom(true)
  } catch (error) {
    console.error('获取历史消息失败', error)
    if (sessionIdAtStart === activeSessionId.value && threadIdAtStart === threadId.value) {
      messages.value = []
    }
  }
}

const reconnectActiveChatRun = async (sessionIdAtStart, threadIdAtStart) => {
  if (!sessionIdAtStart || !threadIdAtStart) {
    isStreaming.value = false
    return
  }

  try {
    const response = await getActiveChatRunAPI(threadIdAtStart)
    if (sessionIdAtStart !== activeSessionId.value || threadIdAtStart !== threadId.value) {
      return
    }
    const run = response?.run
    if (!run) {
      isStreaming.value = false
      return
    }

    sessionStore.setChatRunSnapshot(threadIdAtStart, run)
    const streamState = createStreamState(
      sessionIdAtStart,
      run.run_id,
      threadIdAtStart,
      run.last_event_sequence || 0
    )
    restoreRunOutputSnapshot(streamState, run)
    isStreaming.value = ['queued', 'running'].includes(run.status)
    if (isStreaming.value) {
      void followChatRun(streamState)
    }
  } catch (error) {
    if (sessionIdAtStart === activeSessionId.value && threadIdAtStart === threadId.value) {
      console.error('恢复进行中的对话失败', error)
      isStreaming.value = false
    }
  }
}

watch(
  () => inputText.value,
  (value) => {
    if (value.trim().length > 0) {
      clearSuggestions()
      if (isStreaming.value) {
        skipSuggestionsForCurrentStream.value = true
      }
    }
  }
)

watch(
  () => [activeSessionId.value, threadId.value],
  async ([sessionIdAtStart, threadIdAtStart]) => {
    cancelVoiceTranscriptTypewriter()
    sessionStore.abortAllChatRunSubscriptions()
    isStreaming.value = false
    if (isVoiceRecording.value) {
      discardVoiceRecording()
    }
    clearSuggestions()
    skipSuggestionsForCurrentStream.value = false
    await loadHistory(sessionIdAtStart, threadIdAtStart)
    await reconnectActiveChatRun(sessionIdAtStart, threadIdAtStart)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  cancelVoiceTranscriptTypewriter()
  sessionStore.abortAllChatRunSubscriptions()
  if (isVoiceRecording.value) {
    discardVoiceRecording()
  } else {
    cleanupVoiceRecorder()
  }
  clearSuggestions()
})
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
}

.chat-header {
  height: var(--header-height);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background-color: var(--bg-main);
  z-index: 10;
}



.chat-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-main);
  font-weight: 600;
}

.icon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 6px;
  border-radius: 6px;
  /* display: flex;
  align-items: center; */
  transition: background-color 0.2s;
}

.icon-btn:hover {
  background-color: #f1f5f9;
  color: var(--text-main);
}

.share-btn-icon {
  width: 18px;
  height: 18px;
}

.btn-icon {
  width: 20px;
  height: 20px;
}

.chat-body {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  background-color: #fcfcfd;
  scroll-behavior: smooth;

  &::-webkit-scrollbar {
    width: 10px;
    background: rgba(245,245,245,0.8);
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(73, 61, 206,0.7);
    border: 2px solid #fff;
    border-radius: 5px;
    background-clip: padding-box;
  }
}

.placeholder {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.empty-icon-wrapper {
  background-color: #f1f5f9;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.empty-icon {
  width: 32px;
  height: 32px;
  color: #94a3b8;
}

.empty-state p {
  color: var(--text-main);
  font-size: 15px;
  font-weight: 500;
  margin: 0 0 8px 0;
}

.empty-hint {
  color: var(--text-secondary);
  font-size: 13px;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-bottom: 12px;
}

.message-wrapper {
  display: flex;
  align-items: flex-start;
  max-width: 85%;
}

.message-left {
  align-self: flex-start;
}

.message-right {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar.ai {
  background: linear-gradient(135deg, #e0e7ff, #c7d2fe);
  color: var(--primary-color);
  margin-right: 12px;
}

.avatar.teacher {
  background: linear-gradient(135deg, var(--primary-color), var(--primary-hover));
  color: #ffffff;
  margin-left: 12px;
}

.avatar-icon {
  width: 20px;
  height: 20px;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.message-right .message-content {
  align-items: flex-end;
}

.message-left .message-content {
  align-items: flex-start;
}

.message-bubble {
  padding: 10px 16px;
  font-size: 14px;
  line-height: 1.6;
  border-radius: 12px;
  color: var(--text-main);
  word-wrap: break-word;
}

.message-text-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.message-bubble.is-pending {
  min-width: 54px;
  min-height: 42px;
  display: inline-flex;
  align-items: center;
}

.message-left .message-bubble {
  background-color: #ffffff;
  border: 1px solid var(--border-color);
  border-top-left-radius: 2px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}

.message-right .message-bubble {
  background-color: var(--primary-color);
  color: #ffffff;
  border-top-right-radius: 2px;
  box-shadow: 0 2px 4px rgba(79, 70, 229, 0.2);
}

.message-waiting-dots {
  color: var(--text-disabled);
}

.progress-status-card {
  width: 340px;
  max-width: 100%;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}

.progress-status-card.is-complete {
  background: #ffffff;
}

.progress-status-header {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.progress-status-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.progress-step-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.progress-step-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: var(--text-disabled);
}

.progress-step-item.is-success {
  color: var(--text-secondary);
}

.progress-step-item.is-failed {
  color: #dc2626;
}

.progress-step-indicator {
  width: 18px;
  min-width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #cbd5e1;
}

.step-icon {
  width: 15px;
  height: 15px;
}

.step-icon.success {
  color: #10b981;
}

.step-icon.failed {
  color: #ef4444;
}

.waiting-dots {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.waiting-dots span {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background-color: currentColor;
  opacity: 0.35;
  animation: waiting-dot-bounce 1.2s infinite ease-in-out;
}

.waiting-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.waiting-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

.progress-step-body {
  min-width: 0;
}

.progress-step-label {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
}

.progress-step-detail {
  margin-top: 3px;
  font-size: 12px;
  line-height: 1.45;
  color: inherit;
  opacity: 0.86;
}

.artifact-trace-group {
  width: min(100%, 760px);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.artifact-trace-group-header {
  padding-left: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.artifact-trace-card-row {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.artifact-trace-card-row::-webkit-scrollbar {
  height: 6px;
}

.artifact-trace-card-row::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.36);
}

.artifact-trace-card {
  width: 340px;
  min-width: 340px;
  max-width: 340px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.artifact-trace-card.is-success {
  border-color: rgba(16, 185, 129, 0.24);
}

.artifact-trace-card.is-failed {
  border-color: rgba(239, 68, 68, 0.28);
}

.artifact-trace-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.artifact-trace-card-title {
  min-width: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.artifact-trace-card-status {
  flex-shrink: 0;
  padding: 4px 9px;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.08);
  color: var(--primary-color);
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
}

.artifact-trace-card.is-success .artifact-trace-card-status {
  background: rgba(16, 185, 129, 0.12);
  color: #059669;
}

.artifact-trace-card.is-failed .artifact-trace-card-status {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
}

.artifact-trace-card-subtitle {
  font-size: 12px;
  color: var(--text-disabled);
}

.artifact-trace-timeline {
  max-height: 280px;
  overflow-y: auto;
  padding-right: 4px;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.artifact-trace-timeline::-webkit-scrollbar {
  width: 6px;
}

.artifact-trace-timeline::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.32);
}

.artifact-trace-item {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 10px;
}

.artifact-trace-marker {
  position: relative;
  display: flex;
  justify-content: center;
  padding-top: 2px;
}

.artifact-trace-item:not(:last-child) .artifact-trace-marker::after {
  content: '';
  position: absolute;
  top: 12px;
  bottom: -10px;
  left: 50%;
  width: 1px;
  transform: translateX(-50%);
  background: linear-gradient(180deg, rgba(203, 213, 225, 0.95) 0%, rgba(226, 232, 240, 0.7) 100%);
}

.artifact-trace-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cbd5e1;
  box-shadow: 0 0 0 4px rgba(226, 232, 240, 0.36);
}

.artifact-trace-item.kind-ai_message .artifact-trace-dot {
  background: var(--primary-color);
  box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.12);
}

.artifact-trace-item.kind-tool_call .artifact-trace-dot {
  background: #0f766e;
  box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.12);
}

.artifact-trace-item.kind-tool_result .artifact-trace-dot {
  background: #0284c7;
  box-shadow: 0 0 0 4px rgba(2, 132, 199, 0.12);
}

.artifact-trace-item.status-success .artifact-trace-dot {
  background: #10b981;
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.12);
}

.artifact-trace-item.status-failed .artifact-trace-dot {
  background: #ef4444;
  box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.12);
}

.artifact-trace-body {
  min-width: 0;
  padding-bottom: 12px;
}

.artifact-trace-entry-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.artifact-trace-entry-title {
  min-width: 0;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.45;
  color: var(--text-main);
}

.artifact-trace-toggle {
  flex-shrink: 0;
  border: none;
  background: transparent;
  padding: 0;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: var(--text-disabled);
  font-size: 11px;
  line-height: 1;
  cursor: pointer;
  transition: color 0.16s ease;
}

.artifact-trace-toggle:hover:not(:disabled) {
  color: var(--text-secondary);
}

.artifact-trace-toggle:disabled {
  cursor: default;
  opacity: 0.48;
}

.artifact-trace-toggle-icon {
  width: 12px;
  height: 12px;
}

.artifact-trace-entry-content {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

.approval-card {
  width: 340px;
  max-width: 100%;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.approval-card.is-awaiting-feedback {
  border-color: rgba(79, 70, 229, 0.24);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.06);
}

.approval-card.is-resolved {
  opacity: 0.76;
}

.approval-card-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.approval-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.approval-card-desc {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.approval-metadata-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.approval-metadata-item {
  padding: 10px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid rgba(226, 232, 240, 0.9);
}

.approval-metadata-label {
  font-size: 11px;
  line-height: 1.3;
  color: var(--text-disabled);
}

.approval-metadata-value {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
}

.approval-feedback-hint {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(79, 70, 229, 0.06);
  color: var(--primary-color);
  font-size: 12px;
  line-height: 1.5;
}

.approval-artifact-selector {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.92) 100%);
  border: 1px solid rgba(226, 232, 240, 0.92);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.approval-selector-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-main);
  letter-spacing: 0.01em;
}

.approval-selector-option {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(203, 213, 225, 0.95);
  background: rgba(255, 255, 255, 0.92);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease,
    color 0.18s ease;
}

.approval-selector-option:hover {
  transform: translateY(-1px);
  border-color: rgba(99, 102, 241, 0.32);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
}

.approval-selector-option.is-selected {
  border-color: rgba(79, 70, 229, 0.34);
  background: linear-gradient(180deg, rgba(238, 242, 255, 0.96) 0%, rgba(248, 250, 252, 0.96) 100%);
  color: var(--text-main);
  box-shadow:
    0 10px 22px rgba(79, 70, 229, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.approval-selector-option.is-disabled {
  opacity: 0.58;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.approval-selector-native {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.approval-selector-check {
  width: 18px;
  height: 18px;
  min-width: 18px;
  border-radius: 6px;
  border: 1px solid rgba(148, 163, 184, 0.72);
  background: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    box-shadow 0.18s ease;
}

.approval-selector-check-icon {
  width: 12px;
  height: 12px;
  color: #ffffff;
  opacity: 0;
  transform: scale(0.7);
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}

.approval-selector-option.is-selected .approval-selector-check {
  border-color: var(--primary-color);
  background: linear-gradient(180deg, var(--primary-color) 0%, var(--primary-hover) 100%);
  box-shadow: 0 6px 14px rgba(79, 70, 229, 0.18);
}

.approval-selector-option.is-selected .approval-selector-check-icon {
  opacity: 1;
  transform: scale(1);
}

.approval-selector-option-text {
  line-height: 1.4;
  font-weight: 500;
}

.approval-selector-option:focus-within {
  border-color: rgba(79, 70, 229, 0.38);
  box-shadow:
    0 0 0 3px rgba(79, 70, 229, 0.08),
    0 10px 22px rgba(15, 23, 42, 0.06);
}

.approval-actions {
  display: flex;
  gap: 10px;
}

.approval-btn {
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    background-color 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.approval-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.approval-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.approval-btn-primary {
  border: 1px solid var(--primary-color);
  background: var(--primary-color);
  color: #ffffff;
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.14);
}

.approval-btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
}

.approval-btn-secondary {
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: #ffffff;
  color: var(--text-secondary);
}

.approval-btn-secondary:hover:not(:disabled) {
  border-color: rgba(79, 70, 229, 0.22);
  color: var(--text-main);
}

.message-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.chat-footer {
  position: relative;
  padding: 20px 24px;
  background-color: var(--bg-main);
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.02);
  z-index: 10;
}

.suggestion-layer {
  position: absolute;
  left: 24px;
  right: 24px;
  bottom: calc(100% + 2px);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  pointer-events: none;
  z-index: 30;
}

.suggestion-list {
  pointer-events: auto;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  width: min(860px, 100%);
}

.suggestion-chip {
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: rgba(255, 255, 255, 0.50);
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 12px;
  line-height: 1.3;
  text-align: center;
  cursor: pointer;
  backdrop-filter: blur(6px);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease;
}

.suggestion-chip:hover {
  transform: translateY(-1px);
  color: var(--text-main);
  border-color: rgba(79, 70, 229, 0.22);
  box-shadow: 0 8px 18px rgba(79, 70, 229, 0.08);
}

.suggestion-chip:active {
  transform: translateY(0);
}

@media (max-width: 900px) {
  .suggestion-list {
    grid-template-columns: 1fr;
  }
}

.input-container {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 12px;
  background-color: #ffffff;
  transition: all 0.2s ease;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
}

.input-container:focus-within {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.tool-btn {
  background: transparent;
  border: none;
  display: flex;
  align-items: center;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: all 0.15s;
}

.tool-btn:hover {
  background-color: #f1f5f9;
  color: var(--text-main);
}

.tool-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.tool-btn.is-active {
  background-color: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.tool-btn.is-processing {
  background-color: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.tool-icon {
  width: 16px;
  height: 16px;
  margin-right: 4px;
}

.attachments-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
  padding: 0 4px;
}

.attachment-card {
  display: flex;
  align-items: center;
  background-color: #f8fafc;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--text-main);
}

.attachment-card.is-processing {
  border-color: #c7d2fe;
  background-color: #f8faff;
}

.attachment-card.is-recording {
  border-color: #fda4af;
  background-color: #fff1f2;
}

.attachment-card.is-error {
  border-color: #fecaca;
  background-color: #fef2f2;
}

.attachment-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.attachment-status-text {
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.3;
  margin-top: 2px;
}

.attachment-card.is-error .attachment-status-text {
  color: #ef4444;
}

.sent-attachment {
  background-color: #ffffff;
  border: 1px solid #e2e8f0;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-main);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}

.message-right .sent-attachment {
  background-color: var(--primary-color);
  border: 1px solid var(--primary-hover);
  color: #ffffff;
  box-shadow: 0 2px 4px rgba(79, 70, 229, 0.2);
}

.message-right .sent-attachment .file-icon {
  color: #ffffff;
}

.spinner-icon {
  width: 14px;
  height: 14px;
  margin-right: 6px;
  color: var(--primary-color);
  animation: spin 1s linear infinite;
}

.spin-icon {
  animation: spin 1s linear infinite;
  transform-origin: center;
}

.file-icon {
  width: 14px;
  height: 14px;
  margin-right: 6px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.file-name {
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remove-file-btn {
  background: transparent;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px;
  border-radius: 50%;
  margin-left: 6px;
  cursor: pointer;
  color: #94a3b8;
  margin-right: -4px;
}

.remove-file-btn:hover {
  background-color: #e2e8f0;
  color: #ef4444;
}

.remove-icon {
  width: 12px;
  height: 12px;
}

.chat-input {
  border: none;
  resize: none;
  font-family: inherit;
  font-size: 14px;
  color: var(--text-main);
  padding: 0 4px;
  background: transparent;
  line-height: 1.5;
  outline: none;
}

.chat-input::placeholder {
  color: var(--text-disabled);
}

.suggestion-fade-enter-active,
.suggestion-fade-leave-active {
  transition:
    opacity 0.24s ease,
    transform 0.24s ease;
}

.suggestion-fade-enter-from,
.suggestion-fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

.send-action {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

.send-btn {
  background-color: var(--primary-color);
  color: #ffffff;
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  display: flex;
  align-items: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.send-btn:hover:not(:disabled) {
  background-color: var(--primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(79, 70, 229, 0.3);
}

.send-btn.is-disabled {
  background-color: #cbd5e1;
  cursor: not-allowed;
  opacity: 0.7;
}

.send-icon {
  width: 14px;
  height: 14px;
  margin-right: 6px;
}

.footer-hint {
  text-align: center;
  font-size: 12px;
  color: var(--text-disabled);
  margin-top: 12px;
}

@media (max-width: 720px) {
  .approval-metadata-grid {
    grid-template-columns: 1fr;
  }

  .approval-actions {
    flex-direction: column;
  }
}

@keyframes spin {
  100% {
    transform: rotate(360deg);
  }
}

@keyframes waiting-dot-bounce {
  0%,
  80%,
  100% {
    transform: translateY(0);
    opacity: 0.3;
  }

  40% {
    transform: translateY(-2px);
    opacity: 1;
  }
}
</style>
