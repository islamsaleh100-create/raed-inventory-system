/**
 * Unit tests for CountReviewDialog helpers (TG-COUNT-REVIEW).
 * Run: node --test frontend/src/pages/shift_ops/countReview.test.mjs
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { buildReviewSections } from './CountReviewDialog.jsx'

describe('buildReviewSections', () => {
  const lines = [
    { item_id: 1, received_qty: 10, movement_diff: '2', movement_exception_reason: null },
    { item_id: 2, received_qty: 5, movement_diff: '0', movement_exception_reason: null },
    { item_id: 3, received_qty: 0, movement_diff: '-3', movement_exception_reason: 'سبب اختبار' },
    { item_id: 4, received_qty: 0, movement_diff: '15', movement_exception_reason: null },
    { item_id: 5, received_qty: 0, movement_diff: '9', movement_exception_reason: null },
  ]

  it('counts received items from server lines', () => {
    const r = buildReviewSections(lines)
    assert.equal(r.receivedCount, 2)
    assert.equal(r.received.length, 2)
  })

  it('lists negative lines with server movement_diff', () => {
    const r = buildReviewSections(lines)
    assert.equal(r.negativeCount, 1)
    assert.equal(r.negative[0].movement_diff, '-3')
    assert.equal(r.negative[0].movement_exception_reason, 'سبب اختبار')
  })

  it('top positive is sorted desc max 5', () => {
    const r = buildReviewSections(lines)
    assert.deepEqual(r.topPositive.map((l) => l.item_id), [4, 5, 1])
  })

  it('zero received still returns empty received array', () => {
    const r = buildReviewSections([{ item_id: 9, received_qty: 0, movement_diff: '0' }])
    assert.equal(r.receivedCount, 0)
    assert.equal(r.received.length, 0)
  })
})
