import { UNUSUAL_QTY_WARNING_THRESHOLD } from './shiftCountConstants.js'

/** Accepted qty text after normalization — single optional decimal point. */
export const QTY_ACCEPT_PATTERN = /^\d*\.?\d*$/

const ARABIC_DECIMAL_RE = /[\u066B\u060C\u066C]/g
const EASTERN_ARABIC_DIGIT_RE = /[\u0660-\u0669]/g
const PERSIAN_DIGIT_RE = /[\u06F0-\u06F9]/g

/**
 * Character normalization only — does not reject invalid shapes.
 * ٫ U+066B · ، U+060C · ٬ U+066C → dot · Arabic/Persian digits → 0-9
 * · strip spaces · strip ASCII thousand commas.
 */
export function normalizeQtyInputChars(raw) {
  if (raw === null || raw === undefined) return ''
  let s = String(raw)
  s = s.replace(EASTERN_ARABIC_DIGIT_RE, (ch) => String(ch.charCodeAt(0) - 0x0660))
  s = s.replace(PERSIAN_DIGIT_RE, (ch) => String(ch.charCodeAt(0) - 0x06F0))
  s = s.replace(ARABIC_DECIMAL_RE, '.')
  s = s.replace(/\s/g, '')
  s = s.replace(/,/g, '')
  return s
}

/** Normalize then accept only if the whole string matches QTY_ACCEPT_PATTERN. */
export function processQtyInput(raw) {
  const normalized = normalizeQtyInputChars(raw)
  if (normalized === '') return ''
  if (!QTY_ACCEPT_PATTERN.test(normalized)) return null
  return normalized
}

/** Blur cleanup: ".5" → "0.5" · "5." → "5" */
export function formatQtyOnBlur(raw) {
  if (raw === '' || raw === null || raw === undefined) return raw ?? ''
  let s = String(raw)
  if (s.startsWith('.')) s = `0${s}`
  if (s.endsWith('.')) s = s.slice(0, -1)
  return s
}

export function parseQtyNumber(raw) {
  if (raw === '' || raw === null || raw === undefined) return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

export function isUnusualQty(raw) {
  const n = parseQtyNumber(raw)
  return n !== null && Math.abs(n) >= UNUSUAL_QTY_WARNING_THRESHOLD
}

export { UNUSUAL_QTY_WARNING_THRESHOLD }
