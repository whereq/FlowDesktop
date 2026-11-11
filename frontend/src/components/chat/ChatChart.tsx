import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { ChartSpec } from '../../api/client'

const COLORS = ['var(--color-nova)', 'var(--color-accent)', '#e0a93b', '#d06bd0', '#5bb98c']

/** Inline price chart NOVA renders via the render_chart tool.
 * Single symbol → absolute price; multiple → normalized % change. */
export default function ChatChart({ spec }: { spec: ChartSpec }) {
  if (!spec?.series?.length) return null
  const normalized = spec.normalized && spec.series.length > 1

  // Merge series into rows keyed by date for a shared x-axis.
  const rows: Record<string, Record<string, number | string>> = {}
  for (const s of spec.series) {
    const base = s.points.length ? s.points[0][1] : 0
    for (const [date, val] of s.points) {
      if (!rows[date]) rows[date] = { date }
      rows[date][s.symbol] = normalized && base ? ((val - base) / base) * 100 : val
    }
  }
  const data = Object.values(rows).sort((a, b) => String(a.date).localeCompare(String(b.date)))
  if (!data.length) return null

  const fmtY = (v: number) => normalized ? `${v >= 0 ? '+' : ''}${v.toFixed(0)}%` : v.toFixed(0)

  return (
    <div style={{ border: '1px solid var(--fd-rule)', borderRadius: 2, padding: '8px 8px 4px', background: 'var(--fd-bg-panel)', margin: '6px 0' }}>
      <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--fd-text-faint)', letterSpacing: '0.08em', padding: '0 4px 4px' }}>
        {normalized ? `${spec.days}D · % CHANGE` : `${spec.series[0].symbol} · ${spec.days}D`}
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <XAxis dataKey="date" hide />
          <YAxis width={44} tick={{ fontSize: 10, fill: 'var(--fd-text-faint)' }} tickFormatter={fmtY}
            domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={{ background: 'var(--fd-bg-elev)', border: '1px solid var(--fd-rule)', borderRadius: 2, fontSize: 11 }}
            labelStyle={{ color: 'var(--fd-text-dim)' }}
            formatter={(value) => {
              const n = Number(value)
              return normalized ? `${n >= 0 ? '+' : ''}${n.toFixed(1)}%` : n.toFixed(2)
            }}
          />
          {spec.series.length > 1 && <Legend wrapperStyle={{ fontSize: 10 }} />}
          {spec.series.map((s, i) => (
            <Line key={s.symbol} type="monotone" dataKey={s.symbol} stroke={COLORS[i % COLORS.length]}
              dot={false} strokeWidth={1.6} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
