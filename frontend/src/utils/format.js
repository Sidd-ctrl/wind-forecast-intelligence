export const DASH = '—'

const numberFormatter = new Intl.NumberFormat('en-GB', {
  maximumFractionDigits: 0
})

const oneDecimalFormatter = new Intl.NumberFormat('en-GB', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1
})

const twoDecimalFormatter = new Intl.NumberFormat('en-GB', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
})

export function isNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

export function formatMW(value, digits = 0) {
  if (!isNumber(value)) return DASH
  if (digits === 1) return oneDecimalFormatter.format(value)
  if (digits === 2) return twoDecimalFormatter.format(value)
  return numberFormatter.format(value)
}

export function formatSignedMW(value, digits = 0) {
  if (!isNumber(value)) return DASH
  const magnitude = formatMW(Math.abs(value), digits)
  if (Math.abs(value) < Math.pow(10, -digits) / 2) return magnitude
  return `${value > 0 ? '+' : '-'}${magnitude}`
}

export function formatPct(value, digits = 1) {
  if (!isNumber(value)) return DASH
  return `${value.toFixed(digits)}%`
}

export function formatHours(value, digits = 1) {
  if (!isNumber(value)) return DASH
  return `${value.toFixed(digits)} h`
}

export function formatCount(value) {
  if (!isNumber(value)) return DASH
  return numberFormatter.format(value)
}

export function parseLocalIso(value) {
  if (!value) return null
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function formatLocalDateTime(value, { seconds = false } = {}) {
  const date = parseLocalIso(value)
  if (!date) return DASH
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/London',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: seconds ? '2-digit' : undefined,
    hour12: false
  }).format(date)
}

export function formatLocalTime(value) {
  const date = parseLocalIso(value)
  if (!date) return DASH
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/London',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(date)
}

export function formatDateLong(dateString) {
  if (!dateString) return DASH
  const date = new Date(`${dateString}T12:00:00Z`)
  if (Number.isNaN(date.getTime())) return DASH
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'UTC',
    weekday: 'short',
    day: '2-digit',
    month: 'long',
    year: 'numeric'
  }).format(date)
}

export function formatDateShort(dateString) {
  if (!dateString) return DASH
  const date = new Date(`${dateString}T12:00:00Z`)
  if (Number.isNaN(date.getTime())) return DASH
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'UTC',
    day: '2-digit',
    month: 'short'
  }).format(date)
}

export function directionTag(row) {
  if (row.status !== 'matched') return null
  if (row.direction === 'overforecast') return { className: 'tag--over', label: 'Over' }
  if (row.direction === 'underforecast') return { className: 'tag--under', label: 'Under' }
  return { className: 'tag--exact', label: 'Exact' }
}

export function statusLabel(status) {
  switch (status) {
    case 'matched':
      return 'Matched'
    case 'missing_forecast':
      return 'No forecast'
    case 'missing_actual':
      return 'No actual'
    case 'missing_both':
      return 'No data'
    default:
      return status || DASH
  }
}

export function truncateMiddle(value, head = 34, tail = 12) {
  if (!value || value.length <= head + tail + 3) return value || DASH
  return `${value.slice(0, head)}…${value.slice(-tail)}`
}
