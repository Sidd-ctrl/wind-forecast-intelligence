import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatCount } from '../../utils/format'
import { ChartTooltip } from './ChartTooltip'

const AXIS_COLOR = 'rgba(233,240,234,0.34)'
const GRID_COLOR = 'rgba(233,240,234,0.055)'

export function HistogramChart({ bins, height = 240 }) {
  function TooltipBox({ active, payload }) {
    if (!active || !payload?.length) return null
    const bin = payload[0].payload
    return (
      <ChartTooltip
        title={`${bin.label} MW`}
        rows={[
          { label: 'Periods', value: formatCount(bin.count), color: 'var(--lime)' },
          { label: 'Bin range', value: `${bin.lower_mw.toFixed(0)} – ${bin.upper_mw.toFixed(0)} MW` }
        ]}
      />
    )
  }

  return (
    <div className="chart-frame" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={bins} margin={{ top: 8, right: 8, bottom: 0, left: -18 }} barCategoryGap={2}>
          <CartesianGrid stroke={GRID_COLOR} vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: AXIS_COLOR, fontSize: 9, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'rgba(233,240,234,0.12)' }}
            tickLine={false}
            interval={Math.max(0, Math.floor(bins.length / 8))}
            angle={0}
          />
          <YAxis
            tick={{ fill: AXIS_COLOR, fontSize: 10, fontFamily: 'var(--font-mono)' }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <Tooltip content={<TooltipBox />} cursor={{ fill: 'rgba(233,240,234,0.05)' }} />
          <Bar dataKey="count" fill="#c9f94e" fillOpacity={0.72} name="Periods" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
