import type { ReactNode, CSSProperties } from 'react'

interface PanelProps {
  label?: string
  right?: ReactNode
  children: ReactNode
  style?: CSSProperties
  noBody?: boolean
  className?: string
}

export default function Panel({ label, right, children, style, noBody, className }: PanelProps) {
  return (
    <section
      className={className}
      style={{
        background: 'var(--fd-bg-panel)',
        border: '1px solid var(--fd-rule)',
        ...style,
      }}
    >
      {label && (
        <header
          className="panel-header"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '7px 12px',
            borderBottom: '1px solid var(--fd-rule)',
            color: 'var(--fd-text-dim)',
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            fontFamily: 'var(--font-ui)',
          }}
        >
          <span>{label}</span>
          <span style={{ flex: 1 }} />
          {right}
        </header>
      )}
      {!noBody && <div style={{ padding: 12 }}>{children}</div>}
      {noBody && children}
    </section>
  )
}
