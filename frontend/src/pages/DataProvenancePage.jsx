import { Database, FileWarning, RefreshCw, ShieldCheck } from 'lucide-react'
import { api } from '../services/api'
import { useAnalysisParams } from '../hooks/useAnalysisParams'
import { useDataset } from '../hooks/useDataset'
import { useApiResource } from '../hooks/useApiResource'
import { findNavItem } from '../config/navigation'
import { formatCount, formatLocalDateTime } from '../utils/format'
import { Panel, PanelBody, PanelHead } from '../components/ui/Panel'
import { ErrorState, TableSkeleton } from '../components/ui/States'
import { ControlsResetButton, CutoffControl, ScopeControl } from '../components/controls/WorkspaceControls'

const page = findNavItem('/provenance')

function Fact({ label, value, muted = false }) {
  return (
    <div className="fact">
      <div className="fact__label">{label}</div>
      <div className={`fact__value${muted ? ' fact__value--muted' : ''}`}>{value}</div>
    </div>
  )
}

export function DataProvenancePage() {
  const { selection, selectionKey } = useAnalysisParams()
  const { dataVersion, isRefreshing, refresh } = useDataset()
  const resource = useApiResource(({ signal }) => api.provenance(selection, { signal }), [selectionKey, dataVersion])
  const data = resource.data

  return (
    <>
      <div className="page__head">
        <div>
          <p className="page__eyebrow">{page.eyebrow}</p>
          <h1 className="page__title">
            Data <em>provenance</em>
          </h1>
          <p className="page__desc">{page.description}</p>
        </div>
        <div className="page__meta">
          <div>
            Data mode<strong>{data ? (data.meta.data_mode === 'sample' ? 'Sample snapshot' : 'Live Elexon retrieval') : '—'}</strong>
          </div>
          <div>
            Cache<strong>{data ? data.cache.status : '—'}</strong>
          </div>
        </div>
      </div>

      <div className="stack" style={{ marginTop: 22 }}>
        <Panel>
          <PanelHead title="Selection" hint="Provenance reflects the whole retrieved dataset, not only this selection" />
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

        {resource.isLoading ? <TableSkeleton rows={7} /> : null}
        {resource.status === 'error' ? <ErrorState error={resource.error} onRetry={resource.retry} title="Provenance could not be loaded" /> : null}

        {data ? (
          <>
            <div className="grid-2">
              <Panel>
                <PanelHead title="Retrieval" hint="Recorded by the backend at fetch time">
                  <button type="button" className="btn btn--primary" onClick={refresh} disabled={isRefreshing}>
                    <RefreshCw size={13} className={isRefreshing ? 'spin' : ''} aria-hidden="true" />
                    {isRefreshing ? 'Refreshing' : 'Re-retrieve'}
                  </button>
                </PanelHead>
                <PanelBody>
                  <div className="fact-grid">
                    <Fact label="Retrieved (London)" value={formatLocalDateTime(data.retrieval.retrieval_timestamp_local)} />
                    <Fact label="Retrieved (UTC)" value={data.retrieval.retrieval_timestamp_utc} />
                    <Fact label="Retrieval duration" value={`${formatCount(data.retrieval.duration_ms)} ms`} />
                    <Fact label="Data mode" value={data.meta.data_mode} />
                    <Fact label="Cache status" value={data.cache.status} />
                    <Fact
                      label="Cache age"
                      value={data.cache.age_seconds === null ? 'not cached' : `${formatCount(Math.round(data.cache.age_seconds))} s`}
                    />
                    <Fact label="Cache TTL" value={`${data.cache.ttl_hours} h`} />
                    <Fact label="Cache backend" value={data.cache.backend} muted />
                  </div>
                  <p className="chart-note">{data.cache.note}</p>
                </PanelBody>
              </Panel>

              <Panel>
                <PanelHead title="Analysis range" hint="Configured historical window" />
                <PanelBody>
                  <div className="fact-grid">
                    <Fact label="Delivery start" value={data.analysis_range.start_date} />
                    <Fact label="Delivery end" value={data.analysis_range.end_date} />
                    <Fact label="First publication" value={data.analysis_range.forecast_publish_from ? formatLocalDateTime(data.analysis_range.forecast_publish_from) : '—'} />
                    <Fact label="Latest publication" value={data.analysis_range.forecast_publish_to ? formatLocalDateTime(data.analysis_range.forecast_publish_to) : '—'} />
                    <Fact label="Actual window" value={data.coverage.actual_delivery_window.first ? `${formatLocalDateTime(data.coverage.actual_delivery_window.first)} → ${formatLocalDateTime(data.coverage.actual_delivery_window.last)}` : '—'} />
                    <Fact label="Forecast window" value={data.coverage.forecast_delivery_window.first ? `${formatLocalDateTime(data.coverage.forecast_delivery_window.first)} → ${formatLocalDateTime(data.coverage.forecast_delivery_window.last)}` : '—'} />
                    <Fact label="Distinct publications" value={formatCount(data.coverage.distinct_publications)} />
                    <Fact label="Latest relevant publication" value={data.coverage.latest_forecast_publication ? formatLocalDateTime(data.coverage.latest_forecast_publication) : '—'} />
                  </div>
                </PanelBody>
              </Panel>
            </div>

            <Panel>
              <PanelHead title="Record accounting" hint="Raw records retrieved versus records used after cleaning">
                <span className="tag tag--lime">
                  <Database size={10} aria-hidden="true" />
                  FUELHH · WINDFOR
                </span>
              </PanelHead>
              <PanelBody>
                <div className="fact-grid">
                  <Fact label="Actual records retrieved" value={formatCount(data.counts.actual_records_raw)} />
                  <Fact label="Actual records used" value={formatCount(data.counts.actual_records_used)} />
                  <Fact label="Forecast records retrieved" value={formatCount(data.counts.forecast_records_raw)} />
                  <Fact label="Forecast records used" value={formatCount(data.counts.forecast_records_used)} />
                  <Fact label="Matched observations (selection)" value={formatCount(data.counts.matched_observations)} />
                  <Fact label="Missing actual (selection)" value={formatCount(data.counts.missing_actual)} />
                  <Fact label="Missing forecast (selection)" value={formatCount(data.counts.missing_forecast)} />
                  <Fact label="Duplicate forecasts removed" value={formatCount(data.counts.duplicate_forecasts_removed)} />
                  <Fact label="Duplicate actuals removed" value={formatCount(data.counts.duplicate_actuals_removed)} />
                  <Fact label="Invalid actuals removed" value={formatCount(data.counts.invalid_actuals_removed)} />
                  <Fact label="Invalid forecasts removed" value={formatCount(data.counts.invalid_forecasts_removed)} />
                  <Fact label="Non-WIND rows dropped" value={formatCount(data.duplicates.wrong_fuel_type_dropped)} />
                  <Fact label="Negative actual values" value={formatCount(data.duplicates.negative_actual_values)} />
                  <Fact label="Negative forecast values" value={formatCount(data.duplicates.negative_forecast_values)} />
                </div>
              </PanelBody>
            </Panel>

            <Panel>
              <PanelHead title="Elexon dataset sources" hint="Official BMRS Insights API endpoints" />
              <PanelBody>
                <div className="stack">
                  {data.sources.map((source) => (
                    <div key={source.dataset} style={{ borderLeft: '1px solid var(--hairline)', paddingLeft: 14 }}>
                      <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap', marginBottom: 8 }}>
                        <span className="tag tag--lime">{source.dataset}</span>
                        <strong style={{ fontSize: 13, fontWeight: 500 }}>{source.label}</strong>
                        <span className="tag">{source.granularity}</span>
                      </div>
                      <dl className="kv">
                        <dt>Endpoint</dt>
                        <dd>
                          <a href={source.endpoint} target="_blank" rel="noreferrer" style={{ color: 'var(--lime)' }}>
                            {source.endpoint}
                          </a>
                        </dd>
                        <dt>Documentation</dt>
                        <dd>
                          <a href={source.documentation} target="_blank" rel="noreferrer" style={{ color: 'var(--lime)' }}>
                            bmrs.elexon.co.uk · {source.dataset}
                          </a>
                        </dd>
                        <dt>Parameters</dt>
                        <dd>{source.request_parameters.join(', ')}</dd>
                        <dt>Filter</dt>
                        <dd>{source.filter}</dd>
                        <dt>Fields</dt>
                        <dd>{source.fields.join(', ')}</dd>
                      </dl>
                    </div>
                  ))}
                </div>
              </PanelBody>
            </Panel>

            <div className="grid-2-even">
              <Panel>
                <PanelHead title="Retrieval plan" hint="Chunked to respect the API window limit" />
                <PanelBody flush>
                  <div className="data-table-wrap scroll-area">
                    <table className="data-table">
                      <caption className="sr-only">Retrieval chunks</caption>
                      <thead>
                        <tr>
                          <th scope="col">
                            <span className="th-static">Dataset</span>
                          </th>
                          <th scope="col">
                            <span className="th-static">Window</span>
                          </th>
                          <th scope="col" className="num">
                            <span className="th-static">Records</span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.retrieval.actual_chunks.map((chunk) => (
                          <tr key={`actual-${chunk.label}`}>
                            <td>FUELHH</td>
                            <td>{chunk.label}</td>
                            <td className="num">{formatCount(chunk.record_count)}</td>
                          </tr>
                        ))}
                        {data.retrieval.forecast_chunks.map((chunk) => (
                          <tr key={`forecast-${chunk.label}`}>
                            <td>WINDFOR</td>
                            <td>{chunk.label}</td>
                            <td className="num">{formatCount(chunk.record_count)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </PanelBody>
              </Panel>

              <Panel>
                <PanelHead title="Request parameters" hint="Exactly what was sent to Elexon" />
                <PanelBody>
                  <dl className="kv">
                    <dt>FUELHH</dt>
                    <dd>
                      settlementDateFrom={data.request_parameters.actuals.settlementDateFrom}
                      <br />
                      settlementDateTo={data.request_parameters.actuals.settlementDateTo}
                      <br />
                      fuelType={data.request_parameters.actuals.fuelType}
                    </dd>
                    <dt>WINDFOR</dt>
                    <dd>
                      publishDateTimeFrom={data.request_parameters.forecasts.publishDateTimeFrom}
                      <br />
                      publishDateTimeTo={data.request_parameters.forecasts.publishDateTimeTo}
                    </dd>
                    <dt>Max window</dt>
                    <dd>{data.request_parameters.maximum_window_days_per_request} days per request</dd>
                  </dl>
                  {data.retrieval.actual_request_urls.length ? (
                    <>
                      <div className="divider-label" style={{ marginTop: 16 }}>
                        First request URL
                      </div>
                      <code style={{ fontSize: 10.5, color: 'var(--muted)', wordBreak: 'break-all', fontFamily: 'var(--font-mono)' }}>
                        {data.retrieval.actual_request_urls[0]}
                      </code>
                    </>
                  ) : null}
                </PanelBody>
              </Panel>
            </div>

            <div className="grid-2-even">
              <Panel>
                <PanelHead title="Data-quality warnings" hint="Surfaced from retrieval and normalisation" />
                <PanelBody>
                  {data.warnings.length ? (
                    <div className="list-rows">
                      {data.warnings.map((warning) => (
                        <div className="list-row" key={warning}>
                          <FileWarning size={14} className="list-row__icon" style={{ color: 'var(--amber)' }} aria-hidden="true" />
                          <span>{warning}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="list-row">
                      <ShieldCheck size={14} className="list-row__icon" style={{ color: 'var(--lime)' }} aria-hidden="true" />
                      <span>No data-quality warnings were raised for the retrieved datasets.</span>
                    </div>
                  )}

                  {data.failures.length ? (
                    <>
                      <div className="divider-label" style={{ margin: '16px 0 10px' }}>
                        Retrieval failures
                      </div>
                      <div className="list-rows">
                        {data.failures.map((failure) => (
                          <div className="list-row" key={`${failure.dataset}-${failure.window}`}>
                            <FileWarning size={14} className="list-row__icon" style={{ color: 'var(--crit)' }} aria-hidden="true" />
                            <span>
                              <strong>{failure.dataset}</strong> window {failure.window}: {failure.error}
                            </span>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : null}
                </PanelBody>
              </Panel>

              <Panel>
                <PanelHead title="Known limitations" hint="Interpretation constraints" />
                <PanelBody>
                  <div className="list-rows">
                    {data.limitations.map((limitation) => (
                      <div className="list-row" key={limitation}>
                        <span className="list-row__icon" style={{ color: 'var(--muted)' }}>
                          ·
                        </span>
                        <span>{limitation}</span>
                      </div>
                    ))}
                  </div>
                </PanelBody>
              </Panel>
            </div>
          </>
        ) : null}
      </div>
    </>
  )
}
