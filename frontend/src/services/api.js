const configuredBase = import.meta.env.VITE_API_BASE_URL ?? ''

export const API_BASE_URL = configuredBase.replace(/\/+$/, '')

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'request_failed', details = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function buildQuery(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    if (Array.isArray(value)) {
      value.filter((item) => item !== undefined && item !== null && item !== '').forEach((item) => search.append(key, String(item)))
      return
    }
    search.append(key, String(value))
  })
  const serialised = search.toString()
  return serialised ? `?${serialised}` : ''
}

async function request(path, { params, method = 'GET', signal } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}${buildQuery(params)}`, {
      method,
      signal,
      headers: { Accept: 'application/json' }
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError('The AERON backend could not be reached. Check that the API service is running.', {
      code: 'network_error'
    })
  }

  if (!response.ok) {
    let payload = null
    try {
      payload = await response.json()
    } catch (error) {
      payload = null
    }
    const detail = payload?.error
    throw new ApiError(
      detail?.message || `The backend returned HTTP ${response.status}.`,
      {
        status: response.status,
        code: detail?.code || 'http_error',
        details: detail?.details || null
      }
    )
  }

  return response.json()
}

export function selectionQuery(selection) {
  const query = {
    mode: selection.mode,
    lead_hours: selection.mode === 'rolling_lead' ? selection.leadHours : undefined,
    cutoff: selection.mode === 'absolute_cutoff' ? selection.cutoffUtc : undefined
  }
  if (selection.rangeMode === 'month') {
    return { ...query, start_date: selection.startDate, end_date: selection.endDate }
  }
  return { ...query, delivery_date: selection.deliveryDate }
}

export const api = {
  health: ({ signal } = {}) => request('/health', { signal }),
  metadata: ({ signal } = {}) => request('/api/metadata', { signal }),
  overview: (selection, { signal } = {}) => request('/api/overview', { params: selectionQuery(selection), signal }),
  forecast: (selection, filters = {}, { signal } = {}) =>
    request('/api/forecast', {
      params: { ...selectionQuery(selection), ...filters },
      signal
    }),
  accuracy: (selection, { signal } = {}) => request('/api/accuracy', { params: selectionQuery(selection), signal }),
  compare: (selection, leadHours, absoluteCutoffs, { signal } = {}) =>
    request('/api/accuracy/compare', {
      params: {
        ...selectionQuery({ ...selection, mode: 'rolling_lead' }),
        lead_hours: leadHours,
        cutoff: absoluteCutoffs
      },
      signal
    }),
  provenance: (selection, { signal } = {}) => request('/api/provenance', { params: selectionQuery(selection), signal }),
  records: (selection, { signal } = {}) => request('/api/data/records', { params: selectionQuery(selection), signal }),
  refresh: (selection, { signal } = {}) => request('/api/data/refresh', { params: selectionQuery(selection), method: 'POST', signal }),
  exportUrl: (selection) => `${API_BASE_URL}/api/data/records/export.csv${buildQuery(selectionQuery(selection))}`
}
