function londonOffsetMinutes(date) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/London',
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).formatToParts(date)

  const lookup = parts.reduce((accumulator, part) => {
    accumulator[part.type] = part.value
    return accumulator
  }, {})

  const asLondon = Date.UTC(
    Number(lookup.year),
    Number(lookup.month) - 1,
    Number(lookup.day),
    Number(lookup.hour) % 24,
    Number(lookup.minute),
    Number(lookup.second)
  )

  return (asLondon - date.getTime()) / 60000
}

export function londonNaiveToUtcIso(naiveLocal) {
  if (!naiveLocal) return null
  const normalised = naiveLocal.length === 16 ? `${naiveLocal}:00` : naiveLocal
  const asUtc = new Date(`${normalised}Z`)
  if (Number.isNaN(asUtc.getTime())) return null

  let candidate = new Date(asUtc.getTime() - londonOffsetMinutes(asUtc) * 60000)
  candidate = new Date(asUtc.getTime() - londonOffsetMinutes(candidate) * 60000)
  return candidate.toISOString().replace('.000Z', 'Z')
}

export function shiftDate(dateString, days) {
  const base = new Date(`${dateString}T12:00:00Z`)
  if (Number.isNaN(base.getTime())) return dateString
  base.setUTCDate(base.getUTCDate() + days)
  return base.toISOString().slice(0, 10)
}

export function defaultCutoffFor(deliveryDate) {
  return `${shiftDate(deliveryDate, -1)}T12:00`
}
