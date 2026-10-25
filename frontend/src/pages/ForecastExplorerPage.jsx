import { useEffect, useMemo, useState } from 'react'
import { Download, Filter, Search } from 'lucide-react'
import { api } from '../services/api'
import { useAnalysisParams } from '../hooks/useAnalysisParams'
import { useDataset } from '../hooks/useDataset'
import { useApiResource } from '../hooks/useApiResource'
import { useToast } from '../components/ui/ToastProvider'
import { findNavItem } from '../config/navigation'
import { formatCount, formatMW, formatPct } from '../utils/format'
import { Panel, PanelBody, PanelHead } from '../components/ui/Panel'
import { Readout, ReadoutStrip } from '../components/ui/Readout'
import { EmptyState, ErrorState, TableSkeleton } from '../components/ui/States'
import { ControlsResetButton, CutoffControl, ScopeControl } from '../components/controls/WorkspaceControls'
import { RecordsTable } from '../components/tables/RecordsTable'
import { PublicationDetail } from '../components/panels/PublicationDetail'

const page = findNavItem('/explorer')

const STATUS_OPTIONS = [
  { value: 'all', label: 'All statuses' },
  { value: 'matched', label: 'Matched only' },
  { value: 'missing_forecast', label: 'Missing forecast' },
  { value: 'missing_actual', label: 'Missing actual' },
  { value: 'missing_both', label: 'Missing both' }
]

const DIRECTION_OPTIONS = [
  { value: 'all', label: 'All directions' },
  { value: 'overforecast', label: 'Overforecast' },
  { value: 'underforecast', label: 'Underforecast' },
  { value: 'exact', label: 'Exact match' }
]

export function ForecastExplorerPage() {
  const { selection, selectionKey } = useAnalysisParams()
  const { dataVersion, metricDefinitions } = useDataset()
  const { pushToast } = useToast()

  const [statusFilter, setStatusFilter] = useState('all')
  const [directionFilter, setDirectionFilter] = useState('all')
  const [searchInput, setSearchInput] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [selected, setSelected] = useState(null)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => setSearchTerm(searchInput.trim()), 350)
    return () => window.clearTimeout(timer)
  }, [searchInput])

  const filters = useMemo(
    () => ({ status: statusFilter, direction: directionFilter, search: searchTerm || undefined }),
    [statusFilter, directionFilter, searchTerm]
  )

  const resource = useApiResource(
    ({ signal }) => api.forecast(selection, filters, { signal }),
    [selectionKey, dataVersion, statusFilter, directionFilter, searchTerm]
  )

  const data = resource.data
  const hasLocalFilters = statusFilter !== 'all' || directionFilter !== 'all' || searchInput !== ''

  async function handleExport() {
    setExporting(true)
    try {
      const response = await fetch(api.exportUrl(selection), { headers: { Accept: 'text/csv' } })
      if (!response.ok) {
        throw new Error(`Export failed with HTTP ${response.status}.`)
      }
      const blob = await response.blob()
      const disposition = response.headers.get('content-disposition') || ''
      const match = disposition.match(/filename="?([^";]+)"?/)
      const filename = match ? match[1] : 'aeron-selection.csv'
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
      URL.revokeObjectURL(url)
      pushToast({ text: `CSV export ready · ${filename}` })
    } catch (error) {
      pushToast({ tone: 'error', text: error.message || 'The CSV export could not be generated.' })
    } finally {
      setExporting(false)
    }
  }

  function resetFilters() {
    setStatusFilter('all')
    setDirectionFilter('all')
    setSearchInput('')
    setSearchTerm('')
  }

  return (
    <>
      <div className="page__head">
        <div>
          <p className="page__eyebrow">{page.eyebrow}</p>
          <h1 className="page__title">
            Half-hourly <em>forecast explorer</em>
          </h1>
          <p className="page__desc">{page.description}</p>
        </div>
        <div className="page__meta">
          <div>
            Rows<strong>{data ? formatCount(data.row_count) : '—'}</strong>
          </div>
          <div>
            Cutoff<strong>{data ? (data.selection.mode === 'rolling_lead' ? `T − ${data.selection.lead_hours} h` : 'fixed instant') : '—'}</strong>
          </div>
        </div>
      </div>

      <div className="stack" style={{ marginTop: 22 }}>
        <Panel>
          <PanelHead title="Selection" hint="Applies to the table and the CSV export" />
          <PanelBody>
            <div className="control-bar">
              <ScopeControl />
              <CutoffControl />
              <div className="field">
                <span className="field__label">&nbsp;</span>
                <div className="control-bar__actions">
                  <ControlsResetButton />
                </div>
              </div>
            </div>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHead title="Filters" hint="Applied by the backend before records are returned">
            <span className="tag">
              <Filter size={10} aria-hidden="true" />
              {data ? `${formatCount(data.row_count)} rows` : '—'}
            </span>
            <button type="button" className="btn" onClick={resetFilters} disabled={!hasLocalFilters}>
              Reset filters
            </button>
            <button type="button" className="btn btn--primary" onClick={handleExport} disabled={exporting || !data}>
              <Download size={13} aria-hidden="true" />
              {exporting ? 'Preparing' : 'Export CSV'}
            </button>
          </PanelHead>
          <PanelBody>
            <div className="control-bar">
              <div className="field">
                <label className="field__label" htmlFor="status-filter">
                  Observation status
                </label>
                <select id="status-filter" className="control" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  {STATUS_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="field__label" htmlFor="direction-filter">
                  Error direction
                </label>
                <select
                  id="direction-filter"
                  className="control"
                  value={directionFilter}
                  onChange={(event) => setDirectionFilter(event.target.value)}
                >
                  {DIRECTION_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field" style={{ gridColumn: 'span 2' }}>
                <label className="field__label" htmlFor="search-filter">
                  Search delivery timestamp
                </label>
                <div style={{ position: 'relative' }}>
                  <Search
                    size={13}
                    aria-hidden="true"
                    style={{ position: 'absolute', left: 10, top: 11, color: 'var(--muted-dim)' }}
                  />
                  <input
                    id="search-filter"
                    className="control"
                    style={{ paddingLeft: 30 }}
                    placeholder="e.g. 2026-01-15 14"
                    value={searchInput}
                    onChange={(event) => setSearchInput(event.target.value)}
                  />
                </div>
              </div>
            </div>
          </PanelBody>
        </Panel>

        {resource.isLoading ? <TableSkeleton rows={10} /> : null}
        {resource.status === 'error' ? <ErrorState error={resource.error} onRetry={resource.retry} title="Records could not be loaded" /> : null}

        {data ? (
          <>
            <ReadoutStrip label="Selection summary">
              <Readout label="Matched" value={formatCount(data.quality.matched)} unit={`/ ${formatCount(data.quality.periods_total)}`} tone="accent" foot={`Coverage ${formatPct(data.quality.coverage_pct, 1)}`} />
              <Readout label="Missing forecast" value={formatCount(data.quality.missing_forecast)} foot="No eligible publication before cutoff" />
              <Readout label="Missing actual" value={formatCount(data.quality.missing_actual)} foot="No FUELHH WIND record" />
              <Readout label="Overforecast" value={formatCount(data.metrics.overforecast_count)} tone={data.metrics.overforecast_count > data.metrics.underforecast_count ? 'warn' : 'neutral'} foot={metricDefinitions.overforecast_pct} />
              <Readout label="Underforecast" value={formatCount(data.metrics.underforecast_count)} foot="Forecast below actual" />
              <Readout label="Mean |error|" value={formatMW(data.metrics.mae_mw)} unit="MW" foot={`${formatCount(data.metrics.n_observations)} observations`} />
            </ReadoutStrip>

            <div className={selected ? 'grid-2' : undefined}>
              <Panel>
                <PanelHead title="Selected records" hint="Rows are keyboard navigable · select for publication detail" />
                <PanelBody flush>
                  {data.truncated ? (
                    <p className="chart-note" style={{ padding: '12px 18px 0' }}>
                      The selection exceeds the table limit. Narrow the date range or filters to inspect every record.
                    </p>
                  ) : null}
                  <RecordsTable rows={data.rows} selectedKey={selected?.delivery_local} onSelect={setSelected} caption="Half-hourly forecast, actual and error records" />
                </PanelBody>
              </Panel>

              {selected ? <PublicationDetail row={selected} onClose={() => setSelected(null)} /> : null}
            </div>

            {data.rows.length === 0 ? (
              <EmptyState
                title="No rows match these filters"
                text="The selection itself is valid, but every delivery period was filtered out. Reset the filters to see the full selection."
                action={
                  <button type="button" className="btn" onClick={resetFilters}>
                    Reset filters
                  </button>
                }
              />
            ) : null}
          </>
        ) : null}
      </div>
    </>
  )
}
