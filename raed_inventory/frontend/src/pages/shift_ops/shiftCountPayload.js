/** Pure helpers for shift count PATCH payloads (TG-CLOSING-FRONTEND). */

export const EDITABLE_QTY_FIELDS = ['received_qty', 'returned_qty', 'damaged_qty', 'closing_balance']

export const toNum = (v) => {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

/** DB/UI: closing_balance absent — not the same as stored zero. */
export function closingStored(ln) {
  return (
    ln.closing_balance !== null
    && ln.closing_balance !== undefined
    && String(ln.closing_balance).trim() !== ''
  )
}

export function buildPayloadFromLines(lineArr) {
  return lineArr.map((ln) => {
    const item = { item_id: ln.item_id }
    EDITABLE_QTY_FIELDS.forEach((f) => {
      const v = toNum(ln[f])
      if (v !== null) item[f] = v
    })
    if (ln.movement_exception_reason) item.movement_exception_reason = ln.movement_exception_reason
    if (ln.item_notes) item.item_notes = ln.item_notes
    return item
  })
}

export function countMissingClosing(lineArr) {
  return lineArr.filter((ln) => !closingStored(ln)).length
}
