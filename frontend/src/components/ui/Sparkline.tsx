interface SparklineProps {
  values: number[]
  color?: string
  h?: number
  w?: number
  fill?: boolean
  strokeWidth?: number
}

export default function Sparkline({
  values,
  color = 'currentColor',
  h = 28,
  w = 96,
  fill = false,
  strokeWidth = 1.4,
}: SparklineProps) {
  if (!values || values.length < 2) return null
  const step = w / (values.length - 1)
  const path = values
    .map((v, i) => `${i ? 'L' : 'M'}${(i * step).toFixed(2)} ${(h - (v / 100) * h).toFixed(2)}`)
    .join(' ')
  const area = fill ? `${path} L${w} ${h} L0 ${h} Z` : null
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block', overflow: 'visible' }}>
      {fill && area && <path d={area} fill={color} opacity="0.13" />}
      <path d={path} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

/** Deterministic pseudo-random sparkline points (matching design mock) */
export function generateSparkline(seed: number, count = 24, trend = 0): number[] {
  const pts: number[] = []
  let s = seed * 9301 + 49297
  let v = 50
  for (let i = 0; i < count; i++) {
    s = (s * 9301 + 49297) % 233280
    const r = s / 233280 - 0.5
    v += r * 8 + trend
    pts.push(v)
  }
  const min = Math.min(...pts)
  const max = Math.max(...pts)
  return pts.map(p => ((p - min) / (max - min || 1)) * 100)
}
