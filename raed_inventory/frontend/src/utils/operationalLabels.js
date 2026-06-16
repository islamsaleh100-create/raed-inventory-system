/**
 * Resolve notification / workflow status labels without exposing raw i18n keys.
 */
export function operationalStatusLabel(t, status) {
  if (!status) return ''
  const raw = String(status)
  const candidates = [
    `order_status.${raw}`,
    `order_status.${raw.toLowerCase()}`,
    `branch_request_status.${raw}`,
    `production_order_status.${raw}`,
    `warehouse_line_status.${raw}`,
    `delivery_order_status.${raw}`,
  ]
  for (const key of candidates) {
    const label = t(key)
    if (label && label !== key) return label
  }
  return raw
}

export function notificationSectionLabel(t, key) {
  if (!key) return ''
  const full = `notifications.${key}`
  const label = t(full)
  return label && label !== full ? label : key
}
