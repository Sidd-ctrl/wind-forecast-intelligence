import { X } from 'lucide-react'
import { formatHours, formatLocalDateTime, formatMW, formatSignedMW, statusLabel } from '../../utils/format'

export function PublicationDetail({ row, onClose }) {
  if (!row) return null

  return (
    <aside className="drawer" aria-label="Selected delivery period detail">
      <div className="drawer__head">
        <div>
          <div className="drawer__title">Period {row.period_index}</div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>{formatLocalDateTime(row.delivery_local)}</div>
        </div>
        <button type="button" className="btn btn--ghost btn--icon" onClick={onClose} aria-label="Close detail panel">
          <X size={14} />
        </button>
      </div>

      <dl className="kv">
        <dt>Delivery UTC</dt>
        <dd>{row.delivery_utc}</dd>
        <dt>Settlement</dt>
        <dd>{row.settlement_period === null || row.settlement_period === undefined ? '—' : `SP ${row.settlement_period}`}</dd>
        <dt>Cutoff</dt>
        <dd>{row.cutoff_local ? formatLocalDateTime(row.cutoff_local) : 'per-period cutoff'}</dd>
        <dt>Publication</dt>
        <dd>{row.forecast_publish_local ? formatLocalDateTime(row.forecast_publish_local) : 'none eligible'}</dd>
        <dt>Realised lead</dt>
        <dd>{formatHours(row.lead_hours)}</dd>
        <dt>Forecast</dt>
        <dd>{formatMW(row.forecast_mw)} MW</dd>
        <dt>Actual</dt>
        <dd>{formatMW(row.actual_mw)} MW</dd>
        <dt>Signed error</dt>
        <dd style={{ color: row.error_mw > 0 ? 'var(--amber)' : row.error_mw < 0 ? 'var(--teal)' : 'var(--paper-dim)' }}>
          {formatSignedMW(row.error_mw)} MW
        </dd>
        <dt>Absolute</dt>
        <dd>{formatMW(row.abs_error_mw)} MW</dd>
        <dt>Status</dt>
        <dd>{statusLabel(row.status)}</dd>
        {row.forecast_missing_reason ? (
          <>
            <dt>Missing reason</dt>
            <dd>{row.forecast_missing_reason.replaceAll('_', ' ')}</dd>
          </>
        ) : null}
      </dl>

      <p className="chart-note">
        The forecast shown is the latest WINDFOR publication for this delivery period issued at or before the cutoff. No
        later publication is used, even though it exists in the historical record.
      </p>
    </aside>
  )
}
