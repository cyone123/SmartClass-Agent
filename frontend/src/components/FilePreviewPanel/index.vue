<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="visible" class="preview-overlay" @click.self="handleClose">
        <div class="preview-modal">
          <div class="modal-header">
            <h3>文件预览</h3>
            <div class="header-actions">
              <button class="close-btn" @click="handleClose">
                <X class="icon" />
              </button>
            </div>
          </div>
          <div class="modal-body">
            <div id="onlyoffice-editor" class="editor-container"></div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { nextTick, onBeforeUnmount, watch } from "vue"
import { X } from "lucide-vue-next"

import { getFileConfigAPI } from "@/api/file"

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  fileId: {
    type: [String, Number],
    default: null,
  },
  fileKind: {
    type: String,
    default: "knowledge",
  },
})

const emit = defineEmits(["update:visible"])

let docEditor = null

const initEditor = async () => {
  if (docEditor) {
    docEditor.destroyEditor()
    docEditor = null
  }
  if (!props.fileId || !props.fileKind) {
    return
  }

  try {
    const config = await getFileConfigAPI(props.fileKind, props.fileId)
    await nextTick()
    if (document.getElementById("onlyoffice-editor") && window.DocsAPI) {
      docEditor = new window.DocsAPI.DocEditor("onlyoffice-editor", config)
    }
  } catch (error) {
    console.error("Failed to initialize ONLYOFFICE editor:", error)
  }
}

watch(
  () => [props.visible, props.fileId, props.fileKind],
  async ([visible]) => {
    if (visible) {
      document.body.style.overflow = "hidden"
      await initEditor()
      return
    }

    document.body.style.overflow = ""
    if (docEditor) {
      docEditor.destroyEditor()
      docEditor = null
    }
  },
  { immediate: true }
)

const handleClose = () => {
  emit("update:visible", false)
}

onBeforeUnmount(() => {
  document.body.style.overflow = ""
  if (docEditor) {
    docEditor.destroyEditor()
    docEditor = null
  }
})
</script>

<style scoped>
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
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
  overflow: hidden;
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
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
  transition: all 0.2s;
}

.close-btn:hover {
  background-color: #e2e8f0;
  color: #ef4444;
}

.icon {
  width: 18px;
  height: 18px;
}

.modal-body {
  flex: 1;
  width: 100%;
  position: relative;
  background-color: #f1f5f9;
}

.editor-container {
  position: absolute;
  inset: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-enter-active .preview-modal {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  transform: scale(0.98) translateY(10px);
}

.fade-enter-to .preview-modal {
  transform: scale(1) translateY(0);
}

.fade-leave-active .preview-modal {
  transition: transform 0.3s ease;
}

.fade-leave-to .preview-modal {
  transform: scale(0.98) translateY(10px);
}
</style>
