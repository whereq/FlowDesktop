interface DeltaProps {
  value: number
  size?: number
  withArrow?: boolean
}

export default function Delta({ value, size = 12, withArrow = true }: DeltaProps) {
  const up = value >= 0
  const color = up ? 'var(--color-stock-up)' : 'var(--color-stock-down)'
  return (
    <span
      style={{
        color,
        fontFamily: 'var(--font-mono)',
        fontSize: size,
        fontWeight: 500,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 3,
      }}
    >
      {withArrow && (
        <svg width={size - 1} height={size - 1} viewBox="0 0 12 12" fill="currentColor">
          {up ? (
            <path d="M6 2L10 8H2L6 2Z" />
          ) : (
            <path d="M6 10L2 4H10L6 10Z" />
          )}
        </svg>
      )}
      {(up ? '+' : '') + value.toFixed(2)}%
    </span>
  )
}
