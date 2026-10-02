import { computed, reactive } from "vue"
import { defineStore } from "pinia"

import { getArtifactListAPI } from "@/api/file"

export const useArtifactStore = defineStore("artifact", () => {
  const artifactsByThread = reactive({})

  const getArtifactsByThread = (threadId) => {
    if (!threadId) {
      return []
    }
    return artifactsByThread[threadId] || []
  }

  const setArtifacts = (threadId, artifacts = []) => {
    if (!threadId) {
      return
    }
    artifactsByThread[threadId] = [...artifacts].sort(
      (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
    )
  }

  const upsertArtifact = (artifact) => {
    if (!artifact?.thread_id || !artifact?.id) {
      return
    }

    const current = [...(artifactsByThread[artifact.thread_id] || [])]
    const index = current.findIndex((item) => item.id === artifact.id)
    if (index > -1) {
      current[index] = { ...current[index], ...artifact }
    } else {
      current.unshift(artifact)
    }
    setArtifacts(artifact.thread_id, current)
  }

  const clearArtifacts = () => {
    Object.keys(artifactsByThread).forEach((threadId) => {
      delete artifactsByThread[threadId]
    })
  }

  const fetchArtifacts = async (threadId) => {
    if (!threadId) {
      return []
    }

    const response = await getArtifactListAPI(threadId)
    const artifacts = response?.data || []
    setArtifacts(threadId, artifacts)
    return artifacts
  }

  const currentArtifacts = (threadIdRef) =>
    computed(() => getArtifactsByThread(threadIdRef?.value || threadIdRef))

  return {
    artifactsByThread,
    clearArtifacts,
    currentArtifacts,
    fetchArtifacts,
    getArtifactsByThread,
    setArtifacts,
    upsertArtifact,
  }
})
