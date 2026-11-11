/**
 * FlowDesktop K-Chart F mark — candlestick motif representing "F + ascending chart".
 * Matches Direction A design exactly.
 */
interface FDLogoProps {
  size?: number
  color?: string
  accent?: string
  showWord?: boolean
  weight?: number
  className?: string
}

export default function FDLogo({
  size = 22,
  color = 'currentColor',
  accent = 'var(--color-accent)',
  showWord = true,
  weight = 700,
  className,
}: FDLogoProps) {
  return (
    <span className={className} style={{ display: 'inline-flex', alignItems: 'center', gap: size * 0.4, color }}>
      <svg width={size * 1.18} height={size * 1.18} viewBox="0 0 56 56" fill="none" aria-label="FlowDesktop">
        <rect x="7" y="4" width="5" height="48" rx="1.5" fill="currentColor" />
        {/* K-line top arm: 4 ascending candles */}
        <line x1="18" y1="11" x2="18" y2="22" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <rect x="15.5" y="14" width="5" height="6" rx="0.5" fill="currentColor" />
        <line x1="27" y1="7" x2="27" y2="21" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <rect x="24.5" y="9" width="5" height="10" rx="0.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <line x1="36" y1="3" x2="36" y2="18" stroke={accent} strokeWidth="1.4" strokeLinecap="round" />
        <rect x="33.5" y="5" width="5" height="10" rx="0.5" fill={accent} />
        <line x1="45" y1="2" x2="45" y2="13" stroke={accent} strokeWidth="1.4" strokeLinecap="round" />
        <rect x="42.5" y="3" width="5" height="7" rx="0.5" fill={accent} />
        {/* Middle arm */}
        <rect x="7" y="29" width="22" height="9" rx="1" fill="currentColor" />
        {/* Focus point */}
        <circle cx="9.5" cy="48" r="2.5" fill={accent} />
      </svg>
      {showWord && (
        <span style={{ fontWeight: weight, letterSpacing: '-0.01em', fontSize: size, lineHeight: 1, fontFamily: 'var(--font-ui)' }}>
          Flow<span style={{ opacity: 0.6 }}>Desk</span>
        </span>
      )}
    </span>
  )
}
