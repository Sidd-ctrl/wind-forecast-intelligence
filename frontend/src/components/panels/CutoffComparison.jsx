import { useMemo, useState } from 'react'
import { Scale } from 'lucide-react'
import { api } from '../../services/api'
import { useApiResource } from '../../hooks/useApiResource'
import { formatCount, formatMW, formatPct, formatSignedMW } from '../../utils/format'
import { Panel, PanelBody, PanelHead } from '../ui/Panel'
import { ChartSkeleton, ErrorState } from '../ui/States'
import { CutoffChart } from '../charts/CutoffChart'

const DEFAULT_LEADS = [4, 12, 24, 48]

export function CutoffComparison({ selection, analysisKey, dataVersion, allowedLeadHours }) {
  const [selectedLeads, setSelectedLeads] = useState(DEFAULT_LEADS.filter((lead) => allowedLeadHours.includes(lead)))

  const leads = selectedLeads.length ? selectedLeads : [allowedLeadHours[0]]

  const resource = useApiResource(
    ({ signal }) => api.compare(selection, leads, undefined, { signal }),
    [analysisKey, dataVersion, leads.join(',')]
  )

  const data = resource.data

  const toggleLead = (lead) => {
    setSelectedLeads((current) =>
      current.includes(lead) ? current.filter((value) => value !== lead) : [...current, lead].sort((a, b) => a - b)
    )
  }

  const bestLabel = useMemo(() => {
    if (!data?.common_metrics?.length) return null
    const ranked = data.common_metrics.filter((entry) => entry.mae_mw !== null)
    if (!ranked.length) return null
    return ranked.reduce((best, entry) => (entry.mae_mw < best.mae_mw ? entry : best), ranked[0]).label
  }, [data])

  return (
    <Panel>
      <PanelHead title="Forecast cutoff comparison" hint="Same delivery periods for every cutoff">
        <span className="tag tag--lime">
          <Scale size={10} aria-hidden="true" />
          {data ? `${formatCount(data.common_period_count)} common periods` : '—'}
        </span>
      </PanelHead>
      <PanelBody>
        <div className="stack">
          <div>
            <p className="field__label" style={{ marginBottom: 9 }}>
              Cutoffs included in the comparison
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {allowedLeadHours.map((lead) => {
                const active = selectedLeads.includes(lead)
                return (
                  <button
                    key={lead}
                    type="button"
                    className={`cutoff-option${active ? ' cutoff-option--active' : ''}`}
                    aria-pressed={active}
                    onClick={() => toggleLead(lead)}
                  >
                    <input className="checkbox" type="checkbox" checked={active} readOnly tabIndex={-1} aria-hidden="true" />
                    T − {lead} h
                  </button>
                )
              })}
            </div>
          </div>

          {resource.isLoading ? <ChartSkeleton height={240} /> : null}
          {resource.status === 'error' ? <ErrorState error={resource.error} onRetry={resource.retry} title="Comparison failed" /> : null}

          {data ? (
            <>
              <CutoffChart entries={data.common_metrics} />

              <div className="data-table-wrap">
                <table className="data-table">
                  <caption className="sr-only">Cutoff comparison metrics on common delivery periods</caption>
                  <thead>
                    <tr>
                      <th scope="col">
                        <span className="th-static">Cutoff</span>
                      </th>
                      <th scope="col" className="num">
                        <span className="th-static">Native obs</span>
                      </th>
                      <th scope="col" className="num">
                        <span className="th-static">Common obs</span>
                      </th>
                      <th scope="col" className="num">
                        <span className="th-static">MAE MW</span>
                      </th>
                      <th scope="col" className="num">
                        <span className="th-static">RMSE MW</span>
                      </th>
                      <th scope="col" className="num">
                        <span className="th-static">Bias MW</span>
                      </th>
                      <th scope="col" className="num">
                        <span className="th-static">WAPE</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.entries.map((entry, index) => {
                      const common = data.common_metrics[index]
                      const isBest = entry.label === bestLabel
                      return (
                        <tr key={entry.label}>
                          <td>
                            {entry.label}
                            {isBest ? (
                              <span className="tag tag--lime" style={{ marginLeft: 8 }}>
                                lowest MAE
                              </span>
                            ) : null}
                          </td>
                          <td className="num">{formatCount(entry.n_native)}</td>
                          <td className="num">{formatCount(entry.n_common)}</td>
                          <td className="num">{formatMW(common?.mae_mw)}</td>
                          <td className="num">{formatMW(common?.rmse_mw)}</td>
                          <td className="num">{formatSignedMW(common?.bias_mw)}</td>
                          <td className="num">{common?.wape_pct === null || common?.wape_pct === undefined ? '—' : formatPct(common.wape_pct, 2)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <div
                className="panel"
                style={{ borderColor: 'rgba(201,249,78,0.28)', background: 'rgba(201,249,78,0.04)' }}
              >
                <PanelBody>
                  <p className="panel__title" style={{ marginBottom: 9 }}>
                    Reading the comparison
                  </p>
                  <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.65, color: 'var(--paper-dim)' }}>{data.verdict}</p>
                </PanelBody>
              </div>

              <div className="list-rows">
                {data.disclosures.map((disclosure) => (
                  <div className="list-row" key={disclosure}>
                    <span className="list-row__icon" style={{ color: 'var(--lime)' }}>
                      ·
                    </span>
                    <span>{disclosure}</span>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </div>
      </PanelBody>
    </Panel>
  )
}
