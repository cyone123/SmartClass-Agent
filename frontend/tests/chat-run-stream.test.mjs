import assert from 'node:assert/strict'
import test from 'node:test'

import {
  getSseEventSequence,
  isTerminalRunStatus,
  parseSseEvent,
  shouldApplyRunEvent,
  shouldRetryRunStream,
  splitSseBlocks
} from '../src/api/chatRunStream.js'

test('parses replay sequence, event type, and multiline data', () => {
  const parsed = parseSseEvent('id: 12\nevent: token\ndata: first\ndata: second')
  assert.deepEqual(parsed, { id: '12', event: 'token', data: 'first\nsecond' })
  assert.equal(getSseEventSequence(parsed.id), 12)
})

test('keeps incomplete blocks and ignores already applied sequences', () => {
  const split = splitSseBlocks('id: 1\nevent: token\ndata: a\n\nid: 2\nevent: token')
  assert.equal(split.eventBlocks.length, 1)
  assert.equal(split.rest, 'id: 2\nevent: token')
  assert.equal(shouldApplyRunEvent(3, 3), false)
  assert.equal(shouldApplyRunEvent(3, 4), true)
  assert.equal(shouldApplyRunEvent(3, null), true)
})

test('retries transient Redis readiness failures but stops on permanent client errors', () => {
  assert.equal(shouldRetryRunStream(503), true)
  assert.equal(shouldRetryRunStream(429), true)
  assert.equal(shouldRetryRunStream(0), true)
  assert.equal(shouldRetryRunStream(401), false)
  assert.equal(shouldRetryRunStream(404), false)
})

test('restores monotonically from snapshots and recognizes every terminal status', () => {
  const currentCursor = 7
  const staleSnapshotCursor = 4
  assert.equal(Math.max(currentCursor, staleSnapshotCursor), 7)
  assert.equal(shouldApplyRunEvent(7, 7), false)
  assert.equal(shouldApplyRunEvent(7, 8), true)
  for (const status of ['waiting_approval', 'succeeded', 'failed', 'cancelled']) {
    assert.equal(isTerminalRunStatus(status), true)
  }
  assert.equal(isTerminalRunStatus('running'), false)
})

test('parses one terminal completion and suppresses a duplicate sequence', () => {
  const done = parseSseEvent('id: 9\nevent: done\ndata: {"status":"succeeded"}')
  const sequence = getSseEventSequence(done.id)
  assert.equal(done.event, 'done')
  assert.equal(shouldApplyRunEvent(8, sequence), true)
  assert.equal(shouldApplyRunEvent(sequence, sequence), false)
})

test('keeps metadata and teaching-plan approval payloads compatible', () => {
  const metadataApproval = parseSseEvent(
    'id: 10\nevent: approval\ndata: {"stage":"metadata_review","interrupt_id":"i-1","metadata":{"subject":"Physics","grade":"8","topic":"Gravity"}}'
  )
  const planApproval = parseSseEvent(
    'id: 11\nevent: approval\ndata: {"stage":"teaching_plan_review","interrupt_id":"i-2","artifact_options":[{"type":"ppt","selected":true}]}'
  )
  assert.equal(JSON.parse(metadataApproval.data).stage, 'metadata_review')
  assert.equal(JSON.parse(metadataApproval.data).metadata.topic, 'Gravity')
  assert.equal(JSON.parse(planApproval.data).stage, 'teaching_plan_review')
  assert.equal(JSON.parse(planApproval.data).artifact_options[0].type, 'ppt')
})

test('applies one visible clarification token and suppresses replay duplicates', () => {
  const clarification = parseSseEvent(
    'id: 12\nevent: token\ndata: {"run_id":"run-1","text":"Which grade are you teaching?"}'
  )
  const sequence = getSseEventSequence(clarification.id)
  assert.equal(clarification.event, 'token')
  assert.equal(JSON.parse(clarification.data).text, 'Which grade are you teaching?')
  assert.equal(shouldApplyRunEvent(11, sequence), true)
  assert.equal(shouldApplyRunEvent(sequence, sequence), false)
})

test('protocol-only actions are not represented as visible token events', () => {
  const progress = parseSseEvent(
    'id: 13\nevent: progress\ndata: {"run_id":"run-1","steps":[{"step_key":"metadata_structuring","status":"success"}]}'
  )
  const approval = parseSseEvent(
    'id: 14\nevent: approval\ndata: {"stage":"metadata_review","interrupt_id":"i-3","metadata":{"subject":"Math","grade":"7","topic":"Functions"}}'
  )
  assert.notEqual(progress.event, 'token')
  assert.notEqual(approval.event, 'token')
  assert.equal(progress.data.includes('submit_metadata_for_review'), false)
  assert.equal(approval.data.includes('submit_metadata_for_review'), false)
})
