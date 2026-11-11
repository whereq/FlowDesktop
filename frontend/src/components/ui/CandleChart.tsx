interface OHLCData {
  open: number
  high: number
  low: number
  close: number
}

interface CandleChartProps {
  data: OHLCData[]
  h?: number
  w?: number
  up?: string
  down?: string
  showVol?: boolean
}

export default function CandleChart({
  data,
  h = 200,
  w = 600,
  up = 'var(--color-stock-up)',
  down = 'var(--color-stock-down)',
  showVol = true,
}: CandleChartProps) {
  if (!data || !data.length) return null

  const padL = 44, padR = 12, padT = 12, padB = showVol ? 56 : 24
  const cw = w - padL - padR
  const ch = h - padT - padB
  const hi = Math.max(...data.map(d => d.high))
  const lo = Math.min(...data.map(d => d.low))
  const range = hi - lo || 1
  const bw = cw / data.length
  const y = (v: number) => padT + (1 - (v - lo) / range) * ch

  const yGrid: { v: number; y: number }[] = []
  for (let i = 0; i <= 4; i++) {
    const v = lo + (range * i) / 4
    yGrid.push({ v, y: y(v) })
  }

  const volH = 28
  const grid = 'var(--fd-rule)'
  const axis = 'var(--fd-text-faint)'

  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ display: 'block' }}>
      {yGrid.map((g, i) => (
        <g key={i}>
          <line x1={padL} y1={g.y} x2={w - padR} y2={g.y} stroke={grid} strokeDasharray="2 4" />
          <text x={padL - 6} y={g.y + 3} fill={axis} fontSize="10" textAnchor="end" fontFamily="var(--font-mono)">
            {g.v.toFixed(1)}
          </text>
        </g>
      ))}
      {data.map((d, i) => {
        const x = padL + i * bw + bw * 0.5
        const isUp = d.close >= d.open
        const c = isUp ? up : down
        const yo = y(d.open), yc = y(d.close)
        const yt = Math.min(yo, yc), yb = Math.max(yo, yc)
        const body = Math.max(1, yb - yt)
        const bodyW = Math.max(1.5, bw * 0.62)
        return (
          <g key={i}>
            <line x1={x} y1={y(d.high)} x2={x} y2={y(d.low)} stroke={c} strokeWidth="1" />
            <rect x={x - bodyW / 2} y={yt} width={bodyW} height={body} fill={isUp ? 'transparent' : c} stroke={c} strokeWidth="1" />
          </g>
        )
      })}
      {showVol && data.map((d, i) => {
        const x = padL + i * bw + bw * 0.5
        const isUp = d.close >= d.open
        const c = isUp ? up : down
        const vh = ((Math.abs(d.close - d.open) + 0.6) / 4) * volH
        return <rect key={i} x={x - bw * 0.31} y={h - 14 - vh} width={bw * 0.62} height={vh} fill={c} opacity="0.55" />
      })}
      <line x1={padL} y1={h - 14} x2={w - padR} y2={h - 14} stroke={grid} />
    </svg>
  )
}

/** Generate deterministic OHLC data (for mock/demo purposes) */
export function generateOHLC(seed: number, count = 60): OHLCData[] {
  let s = seed * 9301 + 49297
  let close = 100
  const out: OHLCData[] = []
  for (let i = 0; i < count; i++) {
    s = (s * 9301 + 49297) % 233280; const r1 = s / 233280 - 0.5
    s = (s * 9301 + 49297) % 233280; const r2 = s / 233280 - 0.5
    s = (s * 9301 + 49297) % 233280; const r3 = s / 233280
    const open = close
    close = open + r1 * 4 + Math.sin(i / 6) * 0.6
    const high = Math.max(open, close) + Math.abs(r2) * 3 + r3 * 1.5
    const low = Math.min(open, close) - Math.abs(r2) * 3 - r3 * 1.5
    out.push({ open, high, low, close })
  }
  return out
}
