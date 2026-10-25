import { useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react'
import { formatHours, formatLocalTime, formatMW, formatSignedMW, statusLabel } from '../../utils/format'

const COLUMNS = [
  { key: 'delivery_local', label: 'Delivery (London)', align: 'left', sortable: true },
  { key: 'period_index', label: 'Period', align: 'right', sortable: true },
  { key: 'forecast_mw', label: 'Forecast MW', align: 'right', sortable: true },
  { key: 'actual_mw', label: 'Actual MW', align: 'right', sortable: true },
  { key: 'error_mw', label: 'Error MW', align: 'right', sortable: true },
  { key: 'abs_error_mw', label: '|Error| MW', align: 'right', sortable: true },
  { key: 'forecast_publish_local', label: 'Selected publication', align: 'left', sortable: true },
  { key: 'lead_hours', label: 'Lead h', align: 'right', sortable: true },
  { key: 'status', label: 'Status', align: 'left', sortable: true }
]

function SortIcon({ state }) {
  if (state === 'asc') return <ArrowUp size={11} aria-hidden="true" />
  if (state === 'desc') return <ArrowDown size={11} aria-hidden="true" />
  return <ChevronsUpDown size={11} style={{ opacity: 0.45 }} aria-hidden="true" />
}

function compareRows(left, right, key, direction) {
  const leftValue = left[key]
  const rightValue = right[key]
  const multiplier = direction === 'asc' ? 1 : -1

  if (leftValue === null || leftValue === undefined) return 1
  if (rightValue === null || rightValue === undefined) return -1
  if (typeof leftValue === 'number' && typeof rightValue === 'number') return (leftValue - rightValue) * multiplier
  return String(leftValue).localeCompare(String(rightValue)) * multiplier
}

export function RecordsTable({ rows, selectedKey, onSelect, initialSort = { key: 'delivery_local', direction: 'asc' }, caption }) {
  const [sort, setSort] = useState(initialSort)

  const sorted = useMemo(() => {
    const copy = [...rows]
    copy.sort((left, right) => compareRows(left, right, sort.key, sort.direction))
    return copy
  }, [rows, sort])

  function toggleSort(key) {
    setSort((previous) =>
      previous.key === key
        ? { key, direction: previous.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: 'asc' }
    )
  }

  return (
    <div className="data-table-wrap">
      <table className="data-table">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <th
                key={column.key}
                scope="col"
                aria-sort={sort.key === column.key ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}
                className={column.align === 'right' ? 'num' : undefined}
              >
                <button
                  type="button"
                  className={`th-button${sort.key === column.key ? ' th-button--active' : ''}`}
                  onClick={() => toggleSort(column.key)}
                  style={column.align === 'right' ? { justifyContent: 'flex-end' } : undefined}
                >
                  {column.label}
                  <SortIcon state={sort.key === column.key ? sort.direction : null} />
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={COLUMNS.length} className="table-empty">
                No delivery periods match the current filters.
              </td>
            </tr>
          ) : (
            sorted.map((row) => {
              const key = row.delivery_local
              const isSelected = selectedKey === key
              const isMissing = row.status !== 'matched'
              return (
                <tr
                  key={key}
                  className={`${isSelected ? 'is-selected' : ''}${isMissing ? ' is-missing' : ''}`.trim()}
                  tabIndex={0}
                  onClick={() => onSelect?.(row)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      onSelect?.(row)
                    }
                  }}
                  aria-selected={isSelected}
                >
                  <td>
                    {row.delivery_local.slice(0, 10)} {formatLocalTime(row.delivery_local)}
                  </td>
                  <td className="num">{row.period_index}</td>
                  <td className="num">{formatMW(row.forecast_mw)}</td>
                  <td className="num">{formatMW(row.actual_mw)}</td>
                  <td className={`num ${row.error_mw > 0 ? 'num-over' : row.error_mw < 0 ? 'num-under' : 'num-muted'}`}>
                    {formatSignedMW(row.error_mw)}
                  </td>
                  <td className="num">{formatMW(row.abs_error_mw)}</td>
                  <td>
                    {row.forecast_publish_local ? (
                      <>
                        {row.forecast_publish_local.slice(0, 10)} {formatLocalTime(row.forecast_publish_local)}
                      </>
                    ) : (
                      <span className="num-muted">not published early enough</span>
                    )}
                  </td>
                  <td className="num">{row.lead_hours === null ? '—' : formatHours(row.lead_hours)}</td>
                  <td>
                    {row.status === 'matched' ? (
                      <span className={`tag ${row.direction === 'overforecast' ? 'tag--over' : row.direction === 'underforecast' ? 'tag--under' : 'tag--exact'}`}>
                        {row.direction === 'overforecast' ? 'Over' : row.direction === 'underforecast' ? 'Under' : 'Exact'}
                      </span>
                    ) : (
                      <span className="tag tag--amber">{statusLabel(row.status)}</span>
                    )}
                  </td>
                </tr>
              )
            })
          )}
        </tbody>
      </table>
    </div>
  )
}
