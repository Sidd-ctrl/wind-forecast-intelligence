import { useId } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts'
import { formatMW, formatSignedMW } from '../../utils/format'
import { ChartTooltip } from './ChartTooltip'

const AXIS_COLOR = 'rgba(233,240,234,0.34)'
const GRID_COLOR = 'rgba(233,240,234,0.055)'

export function ForecastChart({ points, band = [], showEnvelope = false, compact = false, height = 330 }) {
  const gradientId = useId().replace(/:/g, '')

  const data = points.map((point, index) => ({
    ...point,
    axisLabel: compact ? point.delivery_local.slice(5, 10) : point.time_label,
    bandLower: showEnvelope ? band[index]?.lower_mw ?? null : null,
    bandUpper: showEnvelope ? band[index]?.upper_mw ?? null : null
  }))

  const tickInterval = Math.max(0, Math.floor(data.length / (compact ? 8 : 12)))

  function TooltipBox({ active, payload }) {
    if (!active || !payload?.length) return null
    const point = payload[0].payload
    return (
      <ChartTooltip
        title={point.delivery_local.replace('T', ' ')}
        rows={[
          { label: 'Actual', value: `${formatMW(point.actual_mw)} MW`, color: 'var(--lime)' },
          { label: 'Forecast at cutoff', value: `${formatMW(point.forecast_mw)} MW`, color: 'var(--paper-dim)' },
          {
            label: 'Signed error',
            value: `${formatSignedMW(point.error_mw)} MW`,
            color: point.error_mw > 0 ? 'var(--amber)' : 'var(--teal)'
          }
        ]}
        foot={
          point.forecast_publish_local
            ? `Published ${point.forecast_publish_local.slice(0, 16).replace('T', ' ')} · lead ${point.lead_hours?.toFixed(1) ?? '—'} h`
            : 'No eligible forecast publication'
        }
      />
    )
  }

  return (
    <div className="chart-frame" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <defs>
            <linearGradient id={`actualFill-${gradientId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#c9f94e" stopOpacity={0.22} />
              <stop offset="100%" stopColor="#c9f94e" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID_COLOR} vertical={false} />
          <XAxis
            dataKey="axisLabel"
            interval={tickInterval}
            tick={{ fill: AXIS_COLOR, fontSize: 10, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'rgba(233,240,234,0.12)' }}
            tickLine={false}
            minTickGap={12}
          />
          <YAxis
            tick={{ fill: AXIS_COLOR, fontSize: 10, fontFamily: 'var(--font-mono)' }}
            axisLine={false}
            tickLine={false}
            width={62}
            tickFormatter={(value) => formatMW(value)}
            domain={[0, 'auto']}
          />
          <Tooltip content={<TooltipBox />} cursor={{ stroke: 'rgba(201,249,78,0.35)', strokeWidth: 1 }} />
          {showEnvelope ? (
            <>
              <Line
                type="monotone"
                dataKey="bandUpper"
                stroke="rgba(233,240,234,0.3)"
                strokeWidth={1}
                strokeDasharray="2 4"
                dot={false}
                isAnimationActive={false}
                name="p95 envelope"
              />
              <Line
                type="monotone"
                dataKey="bandLower"
                stroke="rgba(233,240,234,0.3)"
                strokeWidth={1}
                strokeDasharray="2 4"
                dot={false}
                isAnimationActive={false}
                name="p05 envelope"
              />
            </>
          ) : null}
          <Area
            type="monotone"
            dataKey="actual_mw"
            stroke="#c9f94e"
            strokeWidth={1.8}
            fill={`url(#actualFill-${gradientId})`}
            dot={false}
            connectNulls={false}
            isAnimationActive={data.length < 200}
            name="Actual"
          />
          <Line
            type="monotone"
            dataKey="forecast_mw"
            stroke="#c3cbc1"
            strokeWidth={1.5}
            strokeDasharray="5 4"
            dot={false}
            connectNulls={false}
            isAnimationActive={data.length < 200}
            name="Forecast"
          />
          <ReferenceLine y={0} stroke="rgba(233,240,234,0.18)" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
