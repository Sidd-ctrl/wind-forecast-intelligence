import { Bar, BarChart, Cell, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatMW, formatSignedMW } from '../../utils/format'
import { ChartTooltip } from './ChartTooltip'

const AXIS_COLOR = 'rgba(233,240,234,0.34)'
const GRID_COLOR = 'rgba(233,240,234,0.055)'

export function ErrorChart({ points, compact = false, height = 240 }) {
  const data = points.map((point) => ({
    ...point,
    axisLabel: compact ? point.delivery_local.slice(5, 10) : point.time_label
  }))

  const tickInterval = Math.max(0, Math.floor(data.length / (compact ? 8 : 12)))

  function TooltipBox({ active, payload }) {
    if (!active || !payload?.length) return null
    const point = payload[0].payload
    return (
      <ChartTooltip
        title={point.delivery_local.replace('T', ' ')}
        rows={[
          { label: 'Signed error', value: `${formatSignedMW(point.error_mw)} MW`, color: point.error_mw > 0 ? 'var(--amber)' : 'var(--teal)' },
          { label: 'Absolute error', value: `${formatMW(point.abs_error_mw)} MW` },
          { label: 'Direction', value: point.direction }
        ]}
      />
    )
  }

  return (
    <div className="chart-frame" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }} barCategoryGap={1}>
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
          />
          <Tooltip content={<TooltipBox />} cursor={{ fill: 'rgba(233,240,234,0.05)' }} />
          <ReferenceLine y={0} stroke="rgba(233,240,234,0.28)" />
          <Bar dataKey="error_mw" isAnimationActive={data.length < 200} name="Signed error">
            {data.map((point) => (
              <Cell
                key={point.delivery_local}
                fill={point.error_mw === null ? 'rgba(233,240,234,0.1)' : point.error_mw > 0 ? '#e5a33c' : '#6cb3a8'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
