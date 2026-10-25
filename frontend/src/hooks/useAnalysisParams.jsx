import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { defaultCutoffFor, londonNaiveToUtcIso } from '../utils/timezone'

const ANALYSIS_START = '2026-01-01'
const ANALYSIS_END = '2026-01-31'
const DEFAULT_DELIVERY_DATE = '2026-01-15'
const DEFAULT_LEAD_HOURS = 12

const defaultParams = {
  deliveryDate: DEFAULT_DELIVERY_DATE,
  rangeMode: 'day',
  mode: 'rolling_lead',
  leadHours: DEFAULT_LEAD_HOURS,
  cutoffLocal: defaultCutoffFor(DEFAULT_DELIVERY_DATE),
  startDate: ANALYSIS_START,
  endDate: ANALYSIS_END
}

const AnalysisParamsContext = createContext(null)

export function AnalysisParamsProvider({ children }) {
  const [params, setParams] = useState(defaultParams)

  const setDeliveryDate = useCallback((value) => {
    setParams((previous) => ({
      ...previous,
      deliveryDate: value,
      cutoffLocal: defaultCutoffFor(value)
    }))
  }, [])

  const setRangeMode = useCallback((value) => {
    setParams((previous) => {
      if (value === 'month') {
        return { ...previous, rangeMode: value, mode: 'rolling_lead' }
      }
      return { ...previous, rangeMode: value }
    })
  }, [])

  const setMode = useCallback((value) => {
    setParams((previous) => ({ ...previous, mode: value }))
  }, [])

  const setLeadHours = useCallback((value) => {
    setParams((previous) => ({ ...previous, leadHours: Number(value) }))
  }, [])

  const setCutoffLocal = useCallback((value) => {
    setParams((previous) => ({ ...previous, cutoffLocal: value }))
  }, [])

  const reset = useCallback(() => setParams(defaultParams), [])

  const selection = useMemo(
    () => ({
      deliveryDate: params.deliveryDate,
      startDate: params.startDate,
      endDate: params.endDate,
      rangeMode: params.rangeMode,
      mode: params.rangeMode === 'month' ? 'rolling_lead' : params.mode,
      leadHours: params.leadHours,
      cutoffUtc: londonNaiveToUtcIso(params.cutoffLocal)
    }),
    [params]
  )

  const selectionKey = useMemo(
    () =>
      [
        selection.rangeMode,
        selection.deliveryDate,
        selection.startDate,
        selection.endDate,
        selection.mode,
        selection.leadHours,
        selection.cutoffUtc
      ].join('|'),
    [selection]
  )

  const value = useMemo(
    () => ({
      params: { ...params, analysisStart: ANALYSIS_START, analysisEnd: ANALYSIS_END },
      selection,
      selectionKey,
      setDeliveryDate,
      setRangeMode,
      setMode,
      setLeadHours,
      setCutoffLocal,
      reset,
      isDefault:
        params.deliveryDate === defaultParams.deliveryDate &&
        params.rangeMode === defaultParams.rangeMode &&
        params.mode === defaultParams.mode &&
        params.leadHours === defaultParams.leadHours
    }),
    [params, selection, selectionKey, setDeliveryDate, setRangeMode, setMode, setLeadHours, setCutoffLocal, reset]
  )

  return <AnalysisParamsContext.Provider value={value}>{children}</AnalysisParamsContext.Provider>
}

export function useAnalysisParams() {
  const context = useContext(AnalysisParamsContext)
  if (!context) throw new Error('useAnalysisParams must be used inside AnalysisParamsProvider')
  return context
}
