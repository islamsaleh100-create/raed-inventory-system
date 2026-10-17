/**
 * TG-CLOSING-FRONTEND — shift count payload + missing closing counts.
 * Run: node --test frontend/src/pages/shift_ops/shiftCountPayload.test.mjs
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'
import {
  buildPayloadFromLines,
  closingStored,
  countMissingClosing,
} from './shiftCountPayload.js'

const here = dirname(fileURLToPath(import.meta.url))
const frontendSrcRoot = join(here, '..', '..')
const thisTestFile = fileURLToPath(import.meta.url)
const pageSource = readFileSync(join(here, 'ShiftCountPage.jsx'), 'utf8')

const PROD_EXT = new Set(['.js', '.jsx', '.mjs'])

function isProductionSourceFile(absPath) {
  if (absPath === thisTestFile) return false
  if (/\.test\.(mjs|js)$/i.test(absPath)) return false
  return PROD_EXT.has(absPath.slice(absPath.lastIndexOf('.')))
}

function walkProductionFiles(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const abs = join(dir, name)
    const st = statSync(abs)
    if (st.isDirectory()) {
      if (name === 'node_modules') continue
      walkProductionFiles(abs, out)
    } else if (isProductionSourceFile(abs)) {
      out.push(abs)
    }
  }
  return out
}

function findBuildSubmitPayloadReferences() {
  const hits = []
  for (const file of walkProductionFiles(frontendSrcRoot)) {
    const text = readFileSync(file, 'utf8')
    if (/\bbuildSubmitPayload\b/.test(text)) {
      hits.push(relative(frontendSrcRoot, file))
    }
  }
  return hits
}

describe('T4-1 buildPayloadFromLines — empty closing omits key [unit]', () => {
  it('does not include closing_balance when blank', () => {
    const payload = buildPayloadFromLines([
      { item_id: 1, received_qty: 0, returned_qty: 0, damaged_qty: 0, closing_balance: '' },
    ])
    assert.equal(payload.length, 1)
    assert.equal('closing_balance' in payload[0], false)
  })
})

describe('T4-2 buildPayloadFromLines — explicit zero [unit]', () => {
  it('includes closing_balance: 0', () => {
    const payload = buildPayloadFromLines([
      { item_id: 2, received_qty: 0, returned_qty: 0, damaged_qty: 0, closing_balance: 0 },
    ])
    assert.equal(payload[0].closing_balance, 0)
  })
})

describe('T4-3 ShiftCountPage wiring [static]', () => {
  it('imports shiftCountPayload and uses buildPayloadFromLines in goToReview', () => {
    assert.match(pageSource, /from '\.\/shiftCountPayload\.js'/)
    assert.match(pageSource, /buildPayloadFromLines/)
    assert.doesNotMatch(pageSource, /buildSubmitPayload/)
    assert.match(pageSource, /buildPayloadFromLines\(lines\)/)
  })
})

describe('T4-4-A buildSubmitPayload absent from production frontend/src [static]', () => {
  it('recursive scan of .js/.jsx/.mjs (excludes this test file and *.test.*)', () => {
    const offenders = findBuildSubmitPayloadReferences()
    assert.deepEqual(
      offenders,
      [],
      `buildSubmitPayload must not appear in production sources; found in: ${offenders.join(', ')}`,
    )
  })
})

describe('T16 missingClosing count across states [unit]', () => {
  const line = (id, closing) => ({
    item_id: id,
    received_qty: 0,
    returned_qty: 0,
    damaged_qty: 0,
    closing_balance: closing,
  })

  it('state 1 — incomplete closings counted on all rows', () => {
    const lines = [line(1, ''), line(2, '10'), line(3, '')]
    assert.equal(countMissingClosing(lines), 2)
  })

  it('state 2 — all closings stored', () => {
    const lines = [line(1, '5'), line(2, '0')]
    assert.equal(countMissingClosing(lines), 0)
  })

  it('closingStored distinguishes empty vs zero', () => {
    assert.equal(closingStored(line(1, '')), false)
    assert.equal(closingStored(line(1, 0)), true)
    assert.equal(closingStored(line(1, '0')), true)
  })
})
