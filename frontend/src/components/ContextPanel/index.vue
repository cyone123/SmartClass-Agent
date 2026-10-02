<template>
  <div class="context-container">
    <div class="context-header">
      <h3>资料与生成结果</h3>
      <button class="icon-btn"><Settings2 class="btn-icon" /></button>
    </div>

    <div class="context-body">
      <div class="section">
        <div class="section-title">
          <span>当前会话产物</span>
          <span class="badge">{{ artifacts.length }}</span>
        </div>

        <div class="knowledge-upload-tip">
          <div class="tip-title">支持生成PPT、DOCX教案、HTML5互动教学文件</div>
          <div class="tip-detail">
             生成后的文件支持在线预览与编辑导出，或让AI继续修改。
          </div>
        </div>

        <div class="card-list">
          <div v-if="artifacts.length === 0" class="card empty-card">
            <div class="empty-card-content">
              <FileText class="empty-icon" />
              <span>当前会话还没有产物</span>
            </div>
          </div>

          <div
            v-for="artifact in artifacts"
            :key="artifact.id"
            class="card file-card"
            @click="openArtifact(artifact)"
          >
            <div class="icon-wrapper" :class="getFileIconClass(artifact.extension)">
              <component :is="getFileIcon(artifact.extension)" class="file-icon" />
            </div>

            <div class="file-info">
              <div class="file-name" :title="artifact.title">{{ artifact.title }}</div>
              <div class="file-meta">
                <span class="file-status" :class="getArtifactStatusClass(artifact.status)">
                  <Loader2 v-if="artifact.status === 'running'" class="spin-icon" />
                  {{ getArtifactStatusText(artifact.status) }}
                </span>
                <span class="file-size">{{ formatBytes(artifact.size_bytes) }}</span>
              </div>
              <div v-if="artifact.error_message" class="file-error" :title="artifact.error_message">
                {{ artifact.error_message }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">
          <span>知识库文件</span>
          <span class="badge">{{ knowledgeFiles.length }}</span>
          <div class="section-spacer"></div>
          <button class="icon-btn upload-btn" @click="triggerUpload" :disabled="!activePlanId">
            <Upload class="btn-icon-small" /> 上传
          </button>
          <input
            ref="fileInput"
            type="file"
            :accept="knowledgeFileAccept"
            style="display: none"
            @change="handleFileUpload"
          />
        </div>

        <div class="knowledge-upload-tip">
          <div class="tip-title">支持上传 PDF、DOCX、TXT、MD等文本资料</div>
          <div class="tip-detail">
            {{
              activePlanId
                ? "上传后会自动进入异步解析与向量入库，完成后可在对话中直接检索引用。"
                : "请先在左侧选择一个教学计划，再上传资料进入当前知识库。"
            }}
          </div>
        </div>

        <div class="card-list">
          <div class="card empty-card" v-if="knowledgeFiles.length === 0">
            <div class="empty-card-content">
              <Database class="empty-icon" />
              <span>当前计划下暂无知识库文件</span>
            </div>
          </div>

          <div
            v-for="file in knowledgeFiles"
            :key="file.id"
            class="card file-card"
            @click="openKnowledgeFile(file)"
          >
            <div class="icon-wrapper" :class="getFileIconClass(file.extension)">
              <component :is="getFileIcon(file.extension)" class="file-icon" />
            </div>

            <div class="file-info">
              <div class="file-name" :title="file.original_name">{{ file.original_name }}</div>
              <div class="file-meta">
                <span class="file-status" :class="getKnowledgeStatusClass(file.status)">
                  <Loader2 v-if="['uploaded', 'indexing'].includes(file.status)" class="spin-icon" />
                  {{ getKnowledgeStatusText(file.status) }}
                </span>
                <span class="file-size">{{ formatBytes(file.size_bytes) }}</span>
              </div>
              <div class="file-subtext">
                {{ getKnowledgeStatusDescription(file.status) }}
              </div>
            </div>

            <button class="more-btn delete-btn" @click.stop="deleteFile(file)" title="删除文件">
              <Trash2 class="more-icon" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <FilePreviewPanel
      v-model:visible="isPreviewVisible"
      :file-id="previewFileId"
      :file-kind="previewFileKind"
    />

    <Teleport to="body">
      <Transition name="fade">
        <div v-if="isHtmlPreviewVisible" class="preview-overlay" @click.self="closeHtmlPreview">
          <div class="preview-modal html-preview-modal">
            <div class="modal-header">
              <h3>{{ htmlPreviewTitle || "HTML 互动预览" }}</h3>
              <button class="close-btn" @click="closeHtmlPreview">
                <X class="more-icon" />
              </button>
            </div>
            <div class="html-preview-body">
              <iframe :src="htmlPreviewUrl" title="HTML artifact preview" class="html-preview-frame" />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { storeToRefs } from "pinia"
import {
  Database,
  FileText,
  Loader2,
  Settings2,
  Trash2,
  Upload,
  Video,
  X,
} from "lucide-vue-next"
import { ElMessage, ElMessageBox } from "element-plus"

import FilePreviewPanel from "../FilePreviewPanel/index.vue"
import {
  deleteKnowledgeFileAPI,
  getHtmlArtifactPreviewUrl,
  getKnowledgeFileListAPI,
  uploadKnowledgeFileAPI,
} from "@/api/file"
import { useArtifactStore } from "@/store/artifact"
import { useSessionStore } from "@/store/session"
import { useUserStore } from "@/store/user"

const sessionStore = useSessionStore()
const artifactStore = useArtifactStore()
const userStore = useUserStore()
const { activePlanId, activeThreadId } = storeToRefs(sessionStore)
const { currentUser } = storeToRefs(userStore)

const isPreviewVisible = ref(false)
const previewFileId = ref(null)
const previewFileKind = ref("knowledge")
const knowledgeFiles = ref([])
const fileInput = ref(null)
const isHtmlPreviewVisible = ref(false)
const htmlPreviewUrl = ref("")
const htmlPreviewTitle = ref("")
const knowledgeFileAccept = ".pdf,.docx,.txt,.md,.markdown,.csv,.json"

let pollTimer = null

const artifacts = computed(() => artifactStore.getArtifactsByThread(activeThreadId.value))

const openPreview = (fileKind, fileId) => {
  previewFileKind.value = fileKind
  previewFileId.value = fileId
  isPreviewVisible.value = true
}

const openKnowledgeFile = (file) => {
  if (["uploaded", "indexing", "failed"].includes(file.status)) {
    ElMessage.warning("该知识库文件当前不可预览")
    return
  }
  openPreview("knowledge", file.id)
}

const openArtifact = (artifact) => {
  if (artifact.status !== "ready") {
    ElMessage.warning("当前产物尚未准备完成")
    return
  }

  if (artifact.type === "html-game") {
    htmlPreviewUrl.value = artifact.preview_url || getHtmlArtifactPreviewUrl(artifact.id)
    htmlPreviewTitle.value = artifact.title
    isHtmlPreviewVisible.value = true
    return
  }

  openPreview("artifact", artifact.id)
}

const closeHtmlPreview = () => {
  isHtmlPreviewVisible.value = false
  htmlPreviewUrl.value = ""
  htmlPreviewTitle.value = ""
}

const formatBytes = (bytes) => {
  if (!bytes) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i]
}

const getFileIconClass = (ext) => {
  const normalized = (ext || "").toLowerCase().replace(".", "")
  if (["doc", "docx"].includes(normalized)) return "word-icon"
  if (["pdf"].includes(normalized)) return "pdf-icon"
  if (["xls", "xlsx"].includes(normalized)) return "excel-icon"
  if (["ppt", "pptx"].includes(normalized)) return "ppt-icon"
  if (["html", "htm"].includes(normalized)) return "html-icon"
  if (["mp4", "avi", "mov"].includes(normalized)) return "video-icon"
  return "default-icon"
}

const getFileIcon = (ext) => {
  const normalized = (ext || "").toLowerCase().replace(".", "")
  if (["mp4", "avi", "mov"].includes(normalized)) return Video
  return FileText
}

const getKnowledgeStatusText = (status) => {
  const map = {
    uploaded: "待入库",
    indexing: "入库中",
    ready: "可检索",
    failed: "解析失败",
    deleted: "已删除",
  }
  return map[status] || status
}

const getKnowledgeStatusDescription = (status) => {
  const map = {
    uploaded: "文件已上传，正在等待进入解析队列。",
    indexing: "正在提取文本并写入向量库，请稍候。",
    ready: " ",
    failed: "解析失败，建议检查文件内容后重新上传。",
    deleted: "该文件已从当前知识库移除。",
  }
  return map[status] || "文件状态已更新。"
}

const getKnowledgeStatusClass = (status) => {
  const map = {
    uploaded: "pending",
    indexing: "pending",
    ready: "success",
    failed: "error",
  }
  return map[status] || ""
}

const getArtifactStatusText = (status) => {
  const map = {
    pending: "等待中",
    running: "生成中",
    ready: "已就绪",
    failed: "生成失败",
  }
  return map[status] || status
}

const getArtifactStatusClass = (status) => {
  const map = {
    pending: "pending",
    running: "pending",
    ready: "success",
    failed: "error",
  }
  return map[status] || ""
}

const fetchKnowledgeFiles = async () => {
  if (!activePlanId.value) {
    knowledgeFiles.value = []
    return
  }
  try {
    const res = await getKnowledgeFileListAPI(activePlanId.value)
    knowledgeFiles.value = res.data || []

    const hasPending = knowledgeFiles.value.some((file) => ["uploaded", "indexing"].includes(file.status))
    if (hasPending && !pollTimer) {
      startPolling()
    } else if (!hasPending && pollTimer) {
      stopPolling()
    }
  } catch (error) {
    console.error("获取知识库文件列表失败", error)
  }
}

const fetchArtifacts = async () => {
  if (!activeThreadId.value) {
    artifactStore.clearArtifacts()
    return
  }
  try {
    await artifactStore.fetchArtifacts(activeThreadId.value)
  } catch (error) {
    console.error("获取会话产物失败", error)
  }
}

const startPolling = () => {
  if (!pollTimer) {
    pollTimer = setInterval(fetchKnowledgeFiles, 3000)
  }
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

watch(activePlanId, () => {
  stopPolling()
  fetchKnowledgeFiles()
})

watch(activeThreadId, () => {
  fetchArtifacts()
})

watch(currentUser, (user, previousUser) => {
  if (user?.id === previousUser?.id) {
    return
  }
  stopPolling()
  knowledgeFiles.value = []
  artifactStore.clearArtifacts()

  if (user) {
    fetchKnowledgeFiles()
    fetchArtifacts()
  }
})

onMounted(() => {
  if (activePlanId.value) {
    fetchKnowledgeFiles()
  }
  if (activeThreadId.value) {
    fetchArtifacts()
  }
})

onBeforeUnmount(() => {
  stopPolling()
})

const triggerUpload = () => {
  fileInput.value?.click()
}

const handleFileUpload = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return

  if (!activePlanId.value) {
    ElMessage.warning("请先选择一个教学计划")
    return
  }

  try {
    const res = await uploadKnowledgeFileAPI(activePlanId.value, file)
    if (res.code === 0 || res.data) {
      ElMessage.success("上传成功，资料已加入异步解析与入库队列")
      fetchKnowledgeFiles()
    } else {
      ElMessage.error(res.message || "上传失败")
    }
  } catch (error) {
    console.error(error)
    ElMessage.error("上传出错")
  } finally {
    event.target.value = ""
  }
}

const deleteFile = async (file) => {
  try {
    await ElMessageBox.confirm(`确认删除知识库文件 "${file.original_name}" 吗？`, "删除确认", {
      type: "warning",
    })
    await deleteKnowledgeFileAPI(file.id)
    ElMessage.success("删除成功")
    fetchKnowledgeFiles()
  } catch (error) {
    if (error !== "cancel") {
      console.error(error)
      ElMessage.error("删除失败")
    }
  }
}
</script>

<style scoped>
.context-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
}

.context-header {
  height: var(--header-height);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background-color: var(--bg-context);
}

.context-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
}

.icon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 6px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  transition: background-color 0.2s;
}

.icon-btn:hover {
  background-color: #f1f5f9;
  color: var(--text-main);
}

.btn-icon {
  width: 18px;
  height: 18px;
}

.context-body {
  flex: 1;
  padding: 24px 20px;
  overflow-y: auto;
  background-color: var(--bg-context);

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

.section {
  margin-bottom: 32px;
}

.section-title {
  display: flex;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 16px;
  letter-spacing: 0.5px;
}

.section-spacer {
  flex: 1;
}

.badge {
  background-color: #f1f5f9;
  color: var(--text-secondary);
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  margin-left: 8px;
  font-weight: 500;
}

.knowledge-upload-tip {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid #dbe7ff;
  background: linear-gradient(180deg, #f8fbff 0%, #f3f7ff 100%);
}

.tip-title {
  font-size: 12px;
  font-weight: 600;
  color: #3157b7;
  line-height: 1.5;
}

.tip-detail {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card {
  background-color: #ffffff;
  border-radius: 10px;
  padding: 16px;
  border: 1px solid var(--border-color);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
  transition: all 0.2s ease;
  cursor: pointer;
  position: relative;
}

.card:hover {
  box-shadow: 0 8px 16px -4px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
  border-color: #cbd5e1;
  transform: translateY(-2px);
}

.empty-card {
  border: 1px dashed #cbd5e1;
  background-color: #f8fafc;
  cursor: default;
}

.empty-card:hover {
  transform: none;
  box-shadow: none;
  border-color: var(--text-disabled);
}

.empty-card-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-disabled);
  padding: 16px 0;
  font-size: 13px;
}

.empty-icon {
  width: 24px;
  height: 24px;
  margin-bottom: 8px;
  opacity: 0.6;
}

.file-card {
  display: flex;
  align-items: flex-start;
  padding: 14px 16px;
}

.icon-wrapper {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
  flex-shrink: 0;
}

.word-icon {
  background-color: #eff6ff;
  color: #3b82f6;
}

.excel-icon {
  background-color: #ecfdf5;
  color: #10b981;
}

.ppt-icon {
  background-color: #fef2f2;
  color: #ef4444;
}

.pdf-icon {
  background-color: #fee2e2;
  color: #ef4444;
}

.video-icon {
  background-color: #e0e7ff;
  color: #4f46e5;
}

.html-icon {
  background-color: #fff7ed;
  color: #f97316;
}

.default-icon {
  background-color: #f1f5f9;
  color: #64748b;
}

.file-icon {
  width: 20px;
  height: 20px;
}

.file-info {
  flex: 1;
  overflow: hidden;
  margin-top: 1px;
}

.file-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-main);
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}

.file-meta {
  display: flex;
  align-items: center;
  font-size: 12px;
  gap: 12px;
}

.file-subtext {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--text-secondary);
}

.file-error {
  margin-top: 8px;
  font-size: 12px;
  color: #ef4444;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.file-status {
  display: flex;
  align-items: center;
  font-weight: 500;
}

.file-status.success {
  color: #10b981;
}

.file-status.pending {
  color: #f59e0b;
}

.file-status.error {
  color: #ef4444;
}

.file-size {
  color: var(--text-disabled);
}

.more-btn {
  background: transparent;
  border: none;
  color: var(--text-disabled);
  padding: 4px;
  border-radius: 4px;
  cursor: pointer;
  margin-left: 8px;
  margin-top: -2px;
  margin-right: -8px;
  transition: all 0.2s;
  display: flex;
}

.more-btn:hover {
  color: var(--text-main);
  background-color: #f1f5f9;
}

.more-icon {
  width: 16px;
  height: 16px;
}

.upload-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background-color: var(--primary-color);
  color: white;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.2s;
}

.upload-btn:hover:not(:disabled) {
  background-color: var(--primary-hover);
  color: white;
}

.upload-btn:disabled {
  background-color: #cbd5e1;
  cursor: not-allowed;
}

.btn-icon-small {
  width: 14px;
  height: 14px;
}

.spin-icon {
  width: 12px;
  height: 12px;
  animation: spin 1s linear infinite;
  display: inline-block;
  margin-right: 4px;
  vertical-align: middle;
}

.delete-btn {
  color: #ef4444;
  opacity: 0;
  transition: all 0.2s ease;
}

.card:hover .delete-btn {
  opacity: 0.6;
}

.delete-btn:hover {
  background-color: #fee2e2;
  color: #ef4444 !important;
  opacity: 1 !important;
}

.preview-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-modal {
  width: 90vw;
  height: 90vh;
  max-width: 1400px;
  max-height: 900px;
  background-color: #ffffff;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.html-preview-modal {
  max-width: 1200px;
}

.modal-header {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-color);
  background-color: #f8fafc;
}

.modal-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
}

.close-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
  border-radius: 6px;
}

.close-btn:hover {
  background-color: #e2e8f0;
  color: #ef4444;
}

.html-preview-body {
  flex: 1;
  background-color: #f8fafc;
}

.html-preview-frame {
  width: 100%;
  height: 100%;
  border: none;
  background: #fff;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes spin {
  100% {
    transform: rotate(360deg);
  }
}
</style>
