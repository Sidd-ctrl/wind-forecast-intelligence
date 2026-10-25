import { RotateCcw } from 'lucide-react'
import { useAnalysisParams } from '../../hooks/useAnalysisParams'
import { useDataset } from '../../hooks/useDataset'
import { formatDateShort } from '../../utils/format'
import { InfoTip } from '../ui/InfoTip'

function Segmented({ options, value, onChange, ariaLabel }) {
  return (
    <div className="segmented" role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`segmented__option${option.value === value ? ' segmented__option--active' : ''}`}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export function ScopeControl() {
  const { params, setDeliveryDate, setRangeMode } = useAnalysisParams()
  const { analysisDates } = useDataset()
  const monthMode = params.rangeMode === 'month'

  return (
    <>
      <div className="field">
        <label className="field__label" htmlFor="delivery-date">
          Delivery date
        </label>
        <select
          id="delivery-date"
          className="control"
          value={params.deliveryDate}
          disabled={monthMode}
          onChange={(event) => setDeliveryDate(event.target.value)}
        >
          {analysisDates.map((date) => (
            <option key={date} value={date}>
              {formatDateShort(date)} 2026
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <span className="field__label">Delivery range</span>
        <Segmented
          ariaLabel="Delivery range"
          value={params.rangeMode}
          onChange={setRangeMode}
          options={[
            { value: 'day', label: 'Single day' },
            { value: 'month', label: 'Full month' }
          ]}
        />
      </div>
    </>
  )
}

export function CutoffControl() {
  const { params, setMode, setLeadHours, setCutoffLocal } = useAnalysisParams()
  const { allowedLeadHours, metricDefinitions } = useDataset()
  const monthMode = params.rangeMode === 'month'
  const absoluteMode = params.mode === 'absolute_cutoff' && !monthMode

  return (
    <>
      <div className="field">
        <span className="field__label">
          Cutoff mode
          <InfoTip text={metricDefinitions.cutoff || 'Only publications issued at or before the cutoff are eligible.'} />
        </span>
        <Segmented
          ariaLabel="Cutoff mode"
          value={absoluteMode ? 'absolute_cutoff' : 'rolling_lead'}
          onChange={(value) => setMode(value)}
          options={[
            { value: 'rolling_lead', label: 'Rolling lead' },
            { value: 'absolute_cutoff', label: monthMode ? 'Fixed (day only)' : 'Fixed instant' }
          ]}
        />
      </div>

      {absoluteMode ? (
        <div className="field">
          <label className="field__label" htmlFor="cutoff-instant">
            Decision cutoff · London
          </label>
          <input
            id="cutoff-instant"
            type="datetime-local"
            className="control"
            value={params.cutoffLocal}
            onChange={(event) => setCutoffLocal(event.target.value)}
          />
        </div>
      ) : (
        <div className="field">
          <span className="field__label">Decision cutoff</span>
          <select
            id="lead-hours"
            className="control"
            value={params.leadHours}
            onChange={(event) => setLeadHours(event.target.value)}
            aria-label="Decision cutoff lead time in hours"
          >
            {allowedLeadHours.map((hours) => (
              <option key={hours} value={hours}>
                T − {hours} h
              </option>
            ))}
          </select>
        </div>
      )}
    </>
  )
}

export function ControlsResetButton() {
  const { reset, isDefault } = useAnalysisParams()
  return (
    <button type="button" className="btn" onClick={reset} disabled={isDefault} title="Restore default selection">
      <RotateCcw size={13} aria-hidden="true" />
      Reset filters
    </button>
  )
}

export function WorkspaceControls({ children, showScope = true, showCutoff = true }) {
  return (
    <div className="control-bar">
      {showScope ? <ScopeControl /> : null}
      {showCutoff ? <CutoffControl /> : null}
      {children}
    </div>
  )
}

export function SelectionSummary({ selection }) {
  if (selection.mode === 'rolling_lead') {
    return (
      <span className="tag tag--lime">
        cutoff = T − {selection.leadHours} h
      </span>
    )
  }
  return <span className="tag tag--lime">fixed cutoff instant</span>
}
