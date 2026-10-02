import { defineStore } from 'pinia'
import { markRaw, reactive, ref } from 'vue'

export const useSessionStore = defineStore('session', () => {
  const activeSessionId = ref('')
  const activeThreadId = ref('')
  const activePlanId = ref('')
  const chatRunsByThread = reactive({})

  const getChatRunState = (threadId) => {
    if (!threadId) {
      return null
    }
    if (!chatRunsByThread[threadId]) {
      chatRunsByThread[threadId] = {
        runId: '',
        status: '',
        lastEventSequence: 0,
        outputText: '',
        subscriptionAbortController: null
      }
    }
    return chatRunsByThread[threadId]
  }

  const setChatRunSnapshot = (threadId, run = {}) => {
    const state = getChatRunState(threadId)
    if (!state) {
      return null
    }
    const isSameRun = state.runId === (run.run_id || '')
    state.runId = run.run_id || ''
    state.status = run.status || ''
    state.lastEventSequence = isSameRun
      ? Math.max(state.lastEventSequence || 0, run.last_event_sequence || 0)
      : run.last_event_sequence || 0
    state.outputText = run.output_text || ''
    return state
  }

  const updateChatRunCursor = (threadId, runId, sequence) => {
    const state = getChatRunState(threadId)
    if (!state || (state.runId && state.runId !== runId)) {
      return
    }
    state.runId = runId
    state.lastEventSequence = Math.max(state.lastEventSequence || 0, Number(sequence) || 0)
  }

  const updateChatRunStatus = (threadId, runId, status) => {
    const state = getChatRunState(threadId)
    if (!state || (state.runId && state.runId !== runId)) {
      return
    }
    state.runId = runId
    state.status = status || state.status
  }

  const setChatRunSubscription = (threadId, controller) => {
    const state = getChatRunState(threadId)
    if (!state) {
      return
    }
    if (state.subscriptionAbortController && state.subscriptionAbortController !== controller) {
      state.subscriptionAbortController.abort()
    }
    state.subscriptionAbortController = controller ? markRaw(controller) : null
  }

  const abortChatRunSubscription = (threadId) => {
    const state = getChatRunState(threadId)
    state?.subscriptionAbortController?.abort()
    if (state) {
      state.subscriptionAbortController = null
    }
  }

  const abortAllChatRunSubscriptions = () => {
    Object.keys(chatRunsByThread).forEach((threadId) => abortChatRunSubscription(threadId))
  }
  
  const setActiveSession = (id, threadId = '', planId = '') => {
    activeSessionId.value = id
    activeThreadId.value = threadId
    if (planId) {
      activePlanId.value = planId
    }
  }

  const resetActiveSession = () => {
    activeSessionId.value = ''
    activeThreadId.value = ''
    activePlanId.value = ''
  }
  
  return {
    activeSessionId,
    activeThreadId,
    activePlanId,
    chatRunsByThread,
    abortAllChatRunSubscriptions,
    abortChatRunSubscription,
    getChatRunState,
    resetActiveSession,
    setActiveSession,
    setChatRunSnapshot,
    setChatRunSubscription,
    updateChatRunCursor,
    updateChatRunStatus
  }
})
