export const normalizeSseText = (value = '') => {
  return value.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
}

export const splitSseBlocks = (buffer) => {
  const normalizedBuffer = normalizeSseText(buffer)
  const blocks = normalizedBuffer.split('\n\n')
  return {
    eventBlocks: blocks.slice(0, -1),
    rest: blocks.at(-1) ?? ''
  }
}

export const parseSseEvent = (rawEvent) => {
  const lines = normalizeSseText(rawEvent).split('\n')
  let event = 'message'
  let id = ''
  const dataLines = []

  for (const line of lines) {
    if (!line.trim()) continue
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
      continue
    }
    if (line.startsWith('id:')) {
      id = line.slice(3).trim()
      continue
    }
    if (line.startsWith('data:')) {
      const rawData = line.slice(5)
      dataLines.push(rawData.startsWith(' ') ? rawData.slice(1) : rawData)
    }
  }

  return { id, event, data: dataLines.join('\n') }
}

export const getSseEventSequence = (id) => {
  const sequence = Number(id)
  return Number.isInteger(sequence) && sequence > 0 ? sequence : null
}

export const shouldApplyRunEvent = (lastAppliedSequence, eventSequence) => {
  return eventSequence === null || eventSequence > Math.max(Number(lastAppliedSequence) || 0, 0)
}

export const shouldRetryRunStream = (status) => {
  const normalized = Number(status) || 0
  return normalized === 0 || normalized === 408 || normalized === 429 || normalized >= 500
}

export const isTerminalRunStatus = (status = '') => {
  return ['waiting_approval', 'succeeded', 'failed', 'cancelled'].includes(status)
}
