const labels: Record<string, string> = {
  us: 'US', cn: 'CN', hk: 'HK', tw: 'TW', jp: 'JP', kr: 'KR', uk: 'UK',
  sg: 'SG', ca: 'CA',
}

interface FlagChipProps {
  code: string
  className?: string
}

export default function FlagChip({ code, className }: FlagChipProps) {
  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: 22,
        height: 16,
        padding: '0 5px',
        fontSize: 9.5,
        fontWeight: 600,
        letterSpacing: '0.04em',
        borderRadius: 3,
        border: '1px solid currentColor',
        opacity: 0.7,
        fontFamily: 'var(--font-mono)',
        color: 'var(--fd-text-faint)',
      }}
    >
      {labels[code] || code.toUpperCase()}
    </span>
  )
}
