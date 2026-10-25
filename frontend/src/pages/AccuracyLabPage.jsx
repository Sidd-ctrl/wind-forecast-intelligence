import { api } from '../services/api'
import { useAnalysisParams } from '../hooks/useAnalysisParams'
import { useDataset } from '../hooks/useDataset'
import { useApiResource } from '../hooks/useApiResource'
import { findNavItem } from '../config/navigation'
import { formatCount, formatMW, formatPct, formatSignedMW } from '../utils/format'
import { Panel, PanelBody, PanelHead } from '../components/ui/Panel'
import { Readout, ReadoutStrip } from '../components/ui/Readout'
import { ChartSkeleton, EmptyState, ErrorState, ReadoutSkeleton } from '../components/ui/States'
import { ControlsResetButton, CutoffControl, ScopeControl } from '../components/controls/WorkspaceControls'
import { ErrorChart } from '../components/charts/ErrorChart'
import { HistogramChart } from '../components/charts/HistogramChart'
import { Legend } from '../components/charts/ChartTooltip'
import { CutoffComparison } from '../components/panels/CutoffComparison'

const page = findNavItem('/accuracy')

export function AccuracyLabPage() {
  const { selection, selectionKey, params } = useAnalysisParams()
  const { dataVersion, allowedLeadHours, metricDefinitions } = useDataset()
  const resource = useApiResource(({ signal }) => api.accuracy(selection, { signal }), [selectionKey, dataVersion])
  const data = resource.data
  const compact = params.rangeMode === 'month'

  const direction = data?.direction || { overforecast: 0, underforecast: 0, exact: 0 }
  const directionTotal = direction.overforecast + direction.underforecast + direction.exact || 1

  return (
    <>
      <div className="page__head">
        <div>
          <p className="page__eyebrow">{page.eyebrow}</p>
          <h1 className="page__title">
            Forecast <em>accuracy evaluation</em>
          </h1>
          <p className="page__desc">{page.description}</p>
        </div>
        <div className="page__meta">
          <div>
            Observations<strong>{data ? formatCount(data.metrics.n_observations) : '—'}</strong>
          </div>
          <div>
            Error sign<strong>forecast − actual</strong>
          </div>
        </div>
      </div>

      <div className="stack" style={{ marginTop: 22 }}>
        <Panel>
          <PanelHead title="Selection" hint="Evaluation window">
            {data ? (
              <span className="tag">
                {data.selection.mode === 'rolling_lead' ? `cutoff = T − ${data.selection.lead_hours} h` : 'fixed cutoff instant'}
              </span>
            ) : null}
          </PanelHead>
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

        {resource.isLoading ? <ReadoutSkeleton count={6} /> : null}
        {resource.status === 'error' ? <ErrorState error={resource.error} onRetry={resource.retry} title="Accuracy metrics could not be loaded" /> : null}

        {data ? (
          <>
            <ReadoutStrip>
              <Readout label="MAE" value={formatMW(data.metrics.mae_mw)} unit="MW" tone="accent" tip={metricDefinitions.mae} foot="Mean absolute error" />
              <Readout label="RMSE" value={formatMW(data.metrics.rmse_mw)} unit="MW" tip={metricDefinitions.rmse} foot="Root mean squared error" />
              <Readout
                label="Bias"
                value={formatSignedMW(data.metrics.bias_mw)}
                unit="MW"
                tone={Math.abs(data.metrics.bias_mw || 0) > 0 ? (data.metrics.bias_mw > 0 ? 'warn' : 'neutral') : 'neutral'}
                tip={metricDefinitions.bias}
                foot={data.metrics.bias_mw > 0 ? 'Systematic overforecast' : data.metrics.bias_mw < 0 ? 'Systematic underforecast' : 'Neutral'}
              />
              <Readout
                label="WAPE"
                value={data.metrics.wape_pct === null ? '—' : data.metrics.wape_pct.toFixed(2)}
                unit="%"
                tip={metricDefinitions.wape}
                foot="Relative absolute error"
              />
              <Readout label="Observations" value={formatCount(data.metrics.n_observations)} tip={metricDefinitions.coverage} foot={`Coverage ${formatPct(data.quality.coverage_pct, 1)}`} />
              <Readout
                label="Overforecast"
                value={formatCount(data.metrics.overforecast_count)}
                unit={`/ ${formatCount(data.metrics.n_observations)}`}
                tone={data.metrics.overforecast_count > data.metrics.underforecast_count ? 'warn' : 'neutral'}
                foot={`${formatPct(data.metrics.overforecast_pct, 1)} of matched periods`}
              />
            </ReadoutStrip>

            <div className="grid-2">
              <Panel>
                <PanelHead title="Error by delivery period" hint="Forecast − actual, MW" />
                <PanelBody>
                  {data.by_period.length ? (
                    <>
                      <ErrorChart points={data.by_period} compact={compact} height={280} />
                      <div style={{ marginTop: 12 }}>
                        <Legend
                          items={[
                            { label: 'Overforecast', color: '#e5a33c' },
                            { label: 'Underforecast', color: '#6cb3a8' }
                          ]}
                        />
                      </div>
                      <p className="chart-note">
                        Each bar is one half-hourly delivery period. Bars are absent where no matched observation exists.
                      </p>
                    </>
                  ) : (
                    <EmptyState title="No observations" text="No delivery period in this selection has a matched forecast and actual value." />
                  )}
                </PanelBody>
              </Panel>

              <Panel>
                <PanelHead title="Absolute error distribution" hint={`${formatCount(data.metrics.n_observations)} observations`} />
                <PanelBody>
                  {data.histogram.length ? (
                    <>
                      <HistogramChart bins={data.histogram} height={280} />
                      <p className="chart-note">
                        Distribution of |forecast − actual| across matched delivery periods. A concentrated left tail indicates
                        consistent accuracy; a long right tail indicates occasional large misses.
                      </p>
                    </>
                  ) : (
                    <EmptyState title="No distribution" text="A distribution requires at least one matched observation." />
                  )}
                </PanelBody>
              </Panel>
            </div>

            <div className="grid-2">
              <Panel>
                <PanelHead title="Direction of error" hint="Counts of overforecast and underforecast periods" />
                <PanelBody>
                  <div style={{ display: 'flex', height: 10, borderRadius: 2, overflow: 'hidden', border: '1px solid var(--hairline)' }}>
                    <span style={{ width: `${(direction.overforecast / directionTotal) * 100}%`, background: '#e5a33c' }} title={`Overforecast ${direction.overforecast}`} />
                    <span style={{ width: `${(direction.underforecast / directionTotal) * 100}%`, background: '#6cb3a8' }} title={`Underforecast ${direction.underforecast}`} />
                    <span style={{ width: `${(direction.exact / directionTotal) * 100}%`, background: 'rgba(233,240,234,0.35)' }} title={`Exact ${direction.exact}`} />
                  </div>
                  <div className="fact-grid" style={{ marginTop: 16 }}>
                    <div className="fact">
                      <div className="fact__label">Overforecast</div>
                      <div className="fact__value" style={{ color: 'var(--amber)' }}>{formatCount(direction.overforecast)}</div>
                    </div>
                    <div className="fact">
                      <div className="fact__label">Underforecast</div>
                      <div className="fact__value" style={{ color: 'var(--teal)' }}>{formatCount(direction.underforecast)}</div>
                    </div>
                    <div className="fact">
                      <div className="fact__label">Exact match</div>
                      <div className="fact__value">{formatCount(direction.exact)}</div>
                    </div>
                    <div className="fact">
                      <div className="fact__label">Mean actual</div>
                      <div className="fact__value">{formatMW(data.metrics.mean_actual_mw)} MW</div>
                    </div>
                    <div className="fact">
                      <div className="fact__label">Mean forecast</div>
                      <div className="fact__value">{formatMW(data.metrics.mean_forecast_mw)} MW</div>
                    </div>
                    <div className="fact">
                      <div className="fact__label">Largest |error|</div>
                      <div className="fact__value">{formatMW(data.metrics.max_abs_error_mw)} MW</div>
                    </div>
                  </div>
                </PanelBody>
              </Panel>

              <Panel>
                <PanelHead title="Metric definitions" hint="Formula and sign convention" />
                <PanelBody>
                  <div className="metric-explain">
                    {[
                      ['error', data.explanations.error],
                      ['MAE', data.explanations.mae],
                      ['RMSE', data.explanations.rmse],
                      ['Bias', data.explanations.bias],
                      ['WAPE', data.explanations.wape],
                      ['Lead time', data.explanations.lead_time]
                    ].map(([term, text]) => (
                      <div className="metric-explain__item" key={term}>
                        <div className="metric-explain__term">{term}</div>
                        <div className="metric-explain__text">{text}</div>
                      </div>
                    ))}
                  </div>
                  <div className="list-rows" style={{ marginTop: 14 }}>
                    {data.notes.map((note) => (
                      <div className="list-row" key={note}>
                        <span className="list-row__icon" style={{ color: 'var(--lime)' }}>
                          ·
                        </span>
                        <span>{note}</span>
                      </div>
                    ))}
                  </div>
                </PanelBody>
              </Panel>
            </div>

            <CutoffComparison
              selection={selection}
              analysisKey={selectionKey}
              dataVersion={dataVersion}
              allowedLeadHours={allowedLeadHours}
            />

            <p className="chart-note">{data.scope_note}</p>
          </>
        ) : null}

        {resource.isLoading ? (
          <Panel>
            <PanelHead title="Error diagnostics" />
            <PanelBody>
              <ChartSkeleton />
            </PanelBody>
          </Panel>
        ) : null}
      </div>
    </>
  )
}
