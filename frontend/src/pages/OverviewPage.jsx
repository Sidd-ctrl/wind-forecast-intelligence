import { useMemo, useState } from 'react'
import { ArrowDownRight, ArrowUpRight, Clock3, Crosshair, Layers, Waves } from 'lucide-react'
import { api } from '../services/api'
import { useAnalysisParams } from '../hooks/useAnalysisParams'
import { useDataset } from '../hooks/useDataset'
import { useApiResource } from '../hooks/useApiResource'
import { findNavItem } from '../config/navigation'
import {
  formatCount,
  formatHours,
  formatLocalDateTime,
  formatMW,
  formatPct,
  formatSignedMW
} from '../utils/format'
import { Panel, PanelBody, PanelHead } from '../components/ui/Panel'
import { Readout, ReadoutStrip } from '../components/ui/Readout'
import { ChartSkeleton, EmptyState, ErrorState, ReadoutSkeleton } from '../components/ui/States'
import { ControlsResetButton, ScopeControl, CutoffControl } from '../components/controls/WorkspaceControls'
import { ForecastChart } from '../components/charts/ForecastChart'
import { ErrorChart } from '../components/charts/ErrorChart'
import { Legend } from '../components/charts/ChartTooltip'

const page = findNavItem('/')

export function OverviewPage() {
  const { selection, selectionKey, params } = useAnalysisParams()
  const { dataVersion, metricDefinitions, retrievalLabel, dataMode } = useDataset()
  const [showEnvelope, setShowEnvelope] = useState(false)

  const resource = useApiResource(({ signal }) => api.overview(selection, { signal }), [selectionKey, dataVersion])
  const data = resource.data

  const compact = params.rangeMode === 'month'

  const toneForBias = useMemo(() => {
    if (!data?.metrics) return 'neutral'
    const { bias_mw: bias, mean_actual_mw: mean } = data.metrics
    if (bias === null || !mean) return 'neutral'
    return Math.abs(bias / mean) > 0.05 ? 'warn' : 'neutral'
  }, [data])

  const selectionLabel = useMemo(() => {
    if (!data) return null
    return data.selection.mode === 'rolling_lead'
      ? `Rolling cutoff · T − ${data.selection.lead_hours} h`
      : `Fixed cutoff · ${formatLocalDateTime(data.selection.cutoff_local)}`
  }, [data])

  return (
    <>
      <div className="page__head">
        <div>
          <p className="page__eyebrow">{page.eyebrow}</p>
          <h1 className="page__title">
            Decision-point <em>forecast overview</em>
          </h1>
          <p className="page__desc">{page.description}</p>
        </div>
        <div className="page__meta">
          <div>
            Data mode<strong>{dataMode === 'sample' ? 'Sample snapshot' : 'Historic Elexon retrieval'}</strong>
          </div>
          <div>
            Unit<strong>MW · average over period</strong>
          </div>
          <div>
            Retrieved<strong>{retrievalLabel || '—'}</strong>
          </div>
        </div>
      </div>

      <div className="stack" style={{ marginTop: 22 }}>
        <Panel>
          <PanelHead title="Selection" hint="Decision point applied to every delivery period">
            {selectionLabel ? <span className="tag tag--lime">{selectionLabel}</span> : null}
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

        {resource.status === 'error' ? (
          <ErrorState error={resource.error} onRetry={resource.retry} title="Overview could not be loaded" />
        ) : null}

        {data ? (
          <>
            <ReadoutStrip>
              <Readout
                label="MAE"
                value={formatMW(data.metrics.mae_mw)}
                unit="MW"
                tone="accent"
                tip={metricDefinitions.mae}
                foot={`${formatCount(data.metrics.n_observations)} matched periods`}
              />
              <Readout
                label="RMSE"
                value={formatMW(data.metrics.rmse_mw)}
                unit="MW"
                tip={metricDefinitions.rmse}
                foot="Large misses penalised"
              />
              <Readout
                label="Bias"
                value={formatSignedMW(data.metrics.bias_mw)}
                unit="MW"
                tone={toneForBias}
                tip={metricDefinitions.bias}
                foot={
                  data.metrics.mean_actual_mw
                    ? `${formatSignedMW((data.metrics.bias_mw / data.metrics.mean_actual_mw) * 100, 1)}% of mean actual`
                    : 'Sign: forecast − actual'
                }
              />
              <Readout
                label="WAPE"
                value={data.metrics.wape_pct === null ? '—' : data.metrics.wape_pct.toFixed(2)}
                unit="%"
                tip={metricDefinitions.wape}
                foot="Σ|error| / Σactual"
              />
              <Readout
                label="Matched periods"
                value={formatCount(data.quality.matched)}
                unit={`/ ${formatCount(data.quality.periods_total)}`}
                tip={metricDefinitions.coverage}
                foot={`Coverage ${formatPct(data.quality.coverage_pct, 1)}`}
              />
              <Readout
                label="Overforecast"
                value={data.metrics.overforecast_pct === null ? '—' : data.metrics.overforecast_pct.toFixed(0)}
                unit="%"
                tip={metricDefinitions.overforecast_pct}
                foot={`${formatCount(data.metrics.overforecast_count)} over · ${formatCount(data.metrics.underforecast_count)} under`}
              />
            </ReadoutStrip>

            {data.quality.warnings?.length ? (
              <div className="panel" style={{ borderColor: 'rgba(229,163,60,0.32)' }}>
                <PanelBody>
                  <div className="list-rows">
                    {data.quality.warnings.map((warning) => (
                      <div className="list-row" key={warning}>
                        <span className="list-row__icon" style={{ color: 'var(--amber)' }}>
                          ▲
                        </span>
                        <span>{warning}</span>
                      </div>
                    ))}
                  </div>
                </PanelBody>
              </div>
            ) : null}

            <div className="grid-2">
              <Panel>
                <PanelHead title="Forecast available at cutoff vs actual generation" hint="MW, Europe/London">
                  <button
                    type="button"
                    className={`btn${showEnvelope ? ' btn--primary' : ''}`}
                    onClick={() => setShowEnvelope((value) => !value)}
                    aria-pressed={showEnvelope}
                  >
                    Error envelope
                  </button>
                </PanelHead>
                <PanelBody>
                  {data.series.length ? (
                    <>
                      <ForecastChart
                        points={data.series}
                        band={data.uncertainty.band}
                        showEnvelope={showEnvelope}
                        compact={compact}
                      />
                      <div style={{ marginTop: 12 }}>
                        <Legend
                          items={[
                            { label: 'Actual generation', color: '#c9f94e' },
                            { label: 'Forecast at cutoff', color: '#c3cbc1', dashed: true },
                            ...(showEnvelope
                              ? [{ label: 'Empirical p05–p95 error envelope', color: 'rgba(233,240,234,0.35)', dashed: true }]
                              : [])
                          ]}
                        />
                      </div>
                      <p className="chart-note">
                        Forecast points are the latest WINDFOR publications issued at or before the cutoff for each delivery
                        period. Record gaps are plotted as breaks rather than interpolated values.
                      </p>
                    </>
                  ) : (
                    <EmptyState
                      title="No delivery periods"
                      text="The selected range contains no half-hourly delivery periods. Adjust the delivery date or range."
                    />
                  )}
                </PanelBody>
              </Panel>

              <Panel>
                <PanelHead title="Largest absolute error" hint="Computed from the selected records" />
                <PanelBody>
                  {data.largest_error ? (
                    <div className="stack">
                      <div>
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'baseline',
                            gap: 10,
                            fontFamily: 'var(--font-mono)',
                            fontSize: 30,
                            color: 'var(--amber)',
                            letterSpacing: '-0.02em'
                          }}
                        >
                          {formatMW(data.largest_error.abs_error_mw)}
                          <span style={{ fontSize: 12, color: 'var(--muted-dim)' }}>MW absolute error</span>
                          {data.largest_error.direction === 'overforecast' ? (
                            <ArrowUpRight size={18} style={{ color: 'var(--amber)' }} aria-hidden="true" />
                          ) : (
                            <ArrowDownRight size={18} style={{ color: 'var(--teal)' }} aria-hidden="true" />
                          )}
                        </div>
                        <p style={{ margin: '8px 0 0', fontSize: 12.5, color: 'var(--muted)' }}>
                          {formatLocalDateTime(data.largest_error.delivery_local)} · period{' '}
                          {data.largest_error.period_index}
                        </p>
                      </div>
                      <dl className="kv">
                        <dt>Forecast</dt>
                        <dd>{formatMW(data.largest_error.forecast_mw)} MW</dd>
                        <dt>Actual</dt>
                        <dd>{formatMW(data.largest_error.actual_mw)} MW</dd>
                        <dt>Signed error</dt>
                        <dd style={{ color: data.largest_error.error_mw > 0 ? 'var(--amber)' : 'var(--teal)' }}>
                          {formatSignedMW(data.largest_error.error_mw)} MW
                        </dd>
                        <dt>Published</dt>
                        <dd>{formatLocalDateTime(data.largest_error.forecast_publish_local)}</dd>
                        <dt>Realised lead</dt>
                        <dd>{formatHours(data.largest_error.lead_hours)}</dd>
                      </dl>
                      <div className="divider-label">Interpretation</div>
                      <div className="list-rows">
                        {data.insights.map((insight) => (
                          <div className={`insight insight--${insight.severity}`} key={insight.title}>
                            <span className="insight__bar" aria-hidden="true" />
                            <div>
                              <div className="insight__title">{insight.title}</div>
                              <div className="insight__detail">{insight.detail}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <EmptyState
                      title="No matched observations"
                      text="No delivery period in this selection has both an eligible forecast and an actual record, so no error can be calculated."
                    />
                  )}
                </PanelBody>
              </Panel>
            </div>

            <div className="grid-2">
              <Panel>
                <PanelHead title="Signed error by delivery period" hint="Forecast − actual, MW" />
                <PanelBody>
                  <ErrorChart points={data.series} compact={compact} />
                  <div style={{ marginTop: 12 }}>
                    <Legend
                      items={[
                        { label: 'Overforecast (positive)', color: '#e5a33c' },
                        { label: 'Underforecast (negative)', color: '#6cb3a8' }
                      ]}
                    />
                  </div>
                </PanelBody>
              </Panel>

              <Panel>
                <PanelHead title="Forecast uncertainty" hint="Retrospective error envelope" />
                <PanelBody>
                  <div className="stack">
                    <dl className="kv">
                      <dt>Abs. error p50</dt>
                      <dd>{formatMW(data.uncertainty.abs_error_p50_mw)} MW</dd>
                      <dt>Abs. error p90</dt>
                      <dd>{formatMW(data.uncertainty.abs_error_p90_mw)} MW</dd>
                      <dt>Largest</dt>
                      <dd>{formatMW(data.uncertainty.abs_error_max_mw)} MW</dd>
                      <dt>Signed p05</dt>
                      <dd>{formatSignedMW(data.uncertainty.error_p05_mw)} MW</dd>
                      <dt>Signed p95</dt>
                      <dd>{formatSignedMW(data.uncertainty.error_p95_mw)} MW</dd>
                      <dt>Realised lead</dt>
                      <dd>
                        {formatHours(data.uncertainty.realised_lead_median_hours)} median ·{' '}
                        {data.uncertainty.realised_lead_min_hours !== null
                          ? `${data.uncertainty.realised_lead_min_hours.toFixed(1)}–${data.uncertainty.realised_lead_max_hours.toFixed(1)} h range`
                          : '—'}
                      </dd>
                    </dl>
                    <p className="chart-note">{data.uncertainty.band_basis}</p>
                    <div className="list-rows">
                      <div className="list-row">
                        <Waves size={14} className="list-row__icon" style={{ color: 'var(--lime)' }} aria-hidden="true" />
                        <span>
                          <strong>{formatCount(data.quality.missing_forecast)}</strong> delivery periods had no eligible
                          forecast at this cutoff, and <strong>{formatCount(data.quality.missing_actual)}</strong> had no
                          actual record. These are excluded from every metric above.
                        </span>
                      </div>
                      <div className="list-row">
                        <Layers size={14} className="list-row__icon" style={{ color: 'var(--lime)' }} aria-hidden="true" />
                        <span>
                          WINDFOR publishes hourly delivery targets on an irregular 2–4 hour cycle, so realised lead times
                          vary between delivery periods.
                        </span>
                      </div>
                      <div className="list-row">
                        <Clock3 size={14} className="list-row__icon" style={{ color: 'var(--lime)' }} aria-hidden="true" />
                        <span>
                          Generated {formatLocalDateTime(data.meta.generated_at_local)} from a{' '}
                          {data.meta.data_mode === 'sample' ? 'bundled sample snapshot' : 'historic Elexon retrieval'}.
                        </span>
                      </div>
                      <div className="list-row">
                        <Crosshair size={14} className="list-row__icon" style={{ color: 'var(--lime)' }} aria-hidden="true" />
                        <span>{data.scope_note}</span>
                      </div>
                    </div>
                  </div>
                </PanelBody>
              </Panel>
            </div>
          </>
        ) : null}

        {resource.isLoading ? (
          <Panel>
            <PanelHead title="Forecast vs actual" />
            <PanelBody>
              <ChartSkeleton />
            </PanelBody>
          </Panel>
        ) : null}
      </div>
    </>
  )
}
