import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { api } from '../services/api'
import { useAnalysisParams } from './useAnalysisParams'
import { useApiResource } from './useApiResource'
import { useToast } from '../components/ui/ToastProvider'
import { formatLocalDateTime } from '../utils/format'

const DatasetContext = createContext(null)

const FALLBACK_DATES = Array.from({ length: 31 }, (_, index) => `2026-01-${String(index + 1).padStart(2, '0')}`)

export function DatasetProvider({ children }) {
  const { selection } = useAnalysisParams()
  const { pushToast } = useToast()
  const [dataVersion, setDataVersion] = useState(0)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const health = useApiResource(({ signal }) => api.health({ signal }), [dataVersion])
  const metadata = useApiResource(({ signal }) => api.metadata({ signal }), [dataVersion])

  const refresh = useCallback(async () => {
    setIsRefreshing(true)
    try {
      const result = await api.refresh(selection)
      pushToast({
        tone: 'success',
        text: `Datasets refreshed from Elexon. ${result.counts.actual_records_used.toLocaleString('en-GB')} actual and ${result.counts.forecast_records_used.toLocaleString('en-GB')} forecast records are now cached.`
      })
      setDataVersion((value) => value + 1)
    } catch (error) {
      pushToast({
        tone: 'error',
        text: error.message || 'The refresh request failed. Existing cached data is still being used.'
      })
    } finally {
      setIsRefreshing(false)
    }
  }, [selection, pushToast])

  const value = useMemo(
    () => ({
      dataVersion,
      isRefreshing,
      refresh,
      health: health.data,
      healthError: health.error,
      healthStatus: health.status,
      metadata: metadata.data,
      metadataError: metadata.error,
      metadataStatus: metadata.status,
      analysisDates: metadata.data?.analysis_dates?.length ? metadata.data.analysis_dates : FALLBACK_DATES,
      allowedLeadHours: metadata.data?.allowed_lead_hours?.length ? metadata.data.allowed_lead_hours : [4, 8, 12, 24, 36, 48],
      metricDefinitions: metadata.data?.metric_definitions || {},
      cutoffModes: metadata.data?.cutoff_modes || [],
      scopeNote: metadata.data?.scope_note || '',
      retryHealth: health.retry,
      retryMetadata: metadata.retry,
      dataMode: metadata.data?.meta?.data_mode || health.data?.data_mode || 'unknown',
      retrievalTimestamp: metadata.data?.meta?.cache?.retrieval_timestamp_local || null,
      retrievalLabel: metadata.data?.meta?.cache?.retrieval_timestamp_local
        ? formatLocalDateTime(metadata.data.meta.cache.retrieval_timestamp_local)
        : null,
      cacheStatus: metadata.data?.meta?.cache?.status || health.data?.cache_status || null
    }),
    [dataVersion, isRefreshing, refresh, health, metadata, pushToast]
  )

  return <DatasetContext.Provider value={value}>{children}</DatasetContext.Provider>
}

export function useDataset() {
  const context = useContext(DatasetContext)
  if (!context) throw new Error('useDataset must be used inside DatasetProvider')
  return context
}
