const toNum = (v) => {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

const qtyPositive = (v) => (toNum(v) ?? 0) > 0

/** True when the cashier entered nothing on this line (closing may be 0 or absent). */
export function lineHasNoUserInput(ln) {
  if (qtyPositive(ln.received_qty) || qtyPositive(ln.returned_qty) || qtyPositive(ln.damaged_qty)) {
    return false
  }
  if (String(ln.item_notes || '').trim()) return false
  if (String(ln.movement_exception_reason || '').trim()) return false
  const closing = toNum(ln.closing_balance)
  if (closing !== null && closing !== 0) return false
  return true
}

/** All count lines empty — show extra confirm before submit. One line with any qty ⇒ false. */
export function allRowsHaveNoUserInput(lines = []) {
  return lines.length > 0 && lines.every(lineHasNoUserInput)
}
