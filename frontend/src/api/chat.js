import request from '@/api/index'

export function createChatRunAPI(payload) {
  return request({
    url: 'chat/runs',
    method: 'POST',
    data: payload
  })
}

export function getChatRunAPI(runId) {
  return request({
    url: `chat/runs/${runId}`,
    method: 'GET'
  })
}

export function getActiveChatRunAPI(threadId) {
  return request({
    url: 'chat/runs/active',
    method: 'GET',
    params: { thread_id: threadId }
  })
}

export function cancelChatRunAPI(runId) {
  return request({
    url: `chat/runs/${runId}/cancel`,
    method: 'POST'
  })
}

export function openChatRunEventStream(runId, afterSequence = 0, { signal } = {}) {
  const token = typeof window !== 'undefined' ? window.localStorage.getItem('smartclass_access_token') : ''
  const params = new URLSearchParams({ after_sequence: String(Math.max(Number(afterSequence) || 0, 0)) })
  return fetch(`/api/chat/runs/${encodeURIComponent(runId)}/events?${params.toString()}`, {
    method: 'GET',
    headers: {
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    signal
  })
}
