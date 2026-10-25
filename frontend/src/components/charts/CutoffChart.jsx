import { Bar, BarChart, Cell, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatMW } from '../../utils/format'
import { ChartTooltip } from './ChartTooltip'

const AXIS_COLOR = 'rgba(233,240,234,0.34)'
const GRID_COLOR = 'rgba(233,240,234,0.055)'

export function CutoffChart({ entries, height = 260 }) {
  const data = entries
    .filter((entry) => entry.mae_mw !== null && entry.mae_mw !== undefined)
    .map((entry) => ({
      ...entry,
      shortLabel: entry.lead_hours !== null && entry.lead_hours !== undefined ? `${entry.lead_hours} h` : 'Fixed'
    }))

  if (!data.length) return null

  const best = Math.min(...data.map((entry) => entry.mae_mw))

  function TooltipBox({ active, payload }) {
    if (!active || !payload?.length) return null
    const entry = payload[0].payload
    return (
      <ChartTooltip
        title={entry.label}
        rows={[
          { label: 'MAE (common)', value: `${formatMW(entry.mae_mw)} MW`, color: 'var(--lime)' },
          { label: 'RMSE (common)', value: `${formatMW(entry.rmse_mw)} MW` },
          { label: 'Bias (common)', value: `${formatMW(entry.bias_mw)} MW` },
          { label: 'Observations', value: formatMW(entry.n_observations) }
        ]}
      />
    )
  }

  return (
    <div className="chart-frame" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 22, right: 8, bottom: 0, left: -14 }} barCategoryGap={6}>
          <CartesianGrid stroke={GRID_COLOR} vertical={false} />
          <XAxis
            dataKey="shortLabel"
            tick={{ fill: AXIS_COLOR, fontSize: 10, fontFamily: 'var(--font-mono)' }}
            axisLine={{ stroke: 'rgba(233,240,234,0.12)' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: AXIS_COLOR, fontSize: 10, fontFamily: 'var(--font-mono)' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(value) => formatMW(value)}
            width={62}
          />
          <Tooltip content={<TooltipBox />} cursor={{ fill: 'rgba(233,240,234,0.05)' }} />
          <Bar dataKey="mae_mw" isAnimationActive={false}>
            <LabelList
              dataKey="mae_mw"
              position="top"
              formatter={(value) => formatMW(value)}
              style={{ fill: 'var(--paper-dim)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
            />
            {data.map((entry) => (
              <Cell key={entry.label} fill={entry.mae_mw === best ? '#c9f94e' : 'rgba(201,249,78,0.32)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
