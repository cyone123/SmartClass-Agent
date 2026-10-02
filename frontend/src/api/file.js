import request from "@/api/index"
import axios from "axios"
import { useUserStore } from "@/store/user"

const appendAccessToken = (url) => {
  const token = useUserStore().accessToken
  if (!token) {
    return url
  }
  const separator = url.includes("?") ? "&" : "?"
  return `${url}${separator}access_token=${encodeURIComponent(token)}`
}

export function getFileConfigAPI(fileKind, fileId) {
  return request({
    url: `file/config/${fileKind}/${fileId}`,
    method: "GET",
  })
}

export function getFileDownloadUrl(fileKind, fileId) {
  return appendAccessToken(`/api/file/download/${fileKind}/${fileId}`)
}

export function getHtmlArtifactPreviewUrl(fileId) {
  return appendAccessToken(`/api/file/preview/artifact/${fileId}`)
}

export function forceSaveAPI(key) {
  return axios({
    url: "/savefile/command",
    method: "POST",
    data: {
      c: "forcesave",
      key,
    },
  })
}

export function getKnowledgeFileListAPI(planId) {
  return request({
    url: "file/knowledgeFile",
    method: "GET",
    params: {
      plan_id: planId,
    },
  })
}

export function getArtifactListAPI(threadId) {
  return request({
    url: "file/artifact",
    method: "GET",
    params: {
      thread_id: threadId,
    },
  })
}

export function uploadKnowledgeFileAPI(planId, file) {
  const formData = new FormData()
  formData.append("file", file)

  return request({
    url: "file/knowledgeFile/upload",
    method: "POST",
    params: { plan_id: planId },
    data: formData,
    headers: {
      "Content-Type": "multipart/form-data",
    },
  })
}

export function uploadAttachmentFileAPI(planId, threadId, file) {
  const formData = new FormData()
  formData.append("file", file)

  return request({
    url: "file/attachment/upload",
    method: "POST",
    params: {
      plan_id: planId,
      thread_id: threadId,
    },
    data: formData,
    headers: {
      "Content-Type": "multipart/form-data",
    },
  })
}

export function transcribeVoiceAttachmentAPI(planId, threadId, file) {
  const formData = new FormData()
  formData.append("file", file)

  return request({
    url: "file/attachment/voice/transcribe",
    method: "POST",
    params: {
      plan_id: planId,
      thread_id: threadId,
    },
    data: formData,
    headers: {
      "Content-Type": "multipart/form-data",
    },
  })
}

export function deleteKnowledgeFileAPI(fileId) {
  return request({
    url: `file/${fileId}`,
    method: "DELETE",
  })
}
