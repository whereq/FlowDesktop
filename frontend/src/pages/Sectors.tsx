import { useState, type ReactElement } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import clsx from 'clsx'
import { useSectorThemes, useSectorThemeDetail } from '../hooks/useStocks'
import type { SectorTheme } from '../api/client'

// ── Icons ─────────────────────────────────────────────────────────────────────

const SECTOR_ICONS: Record<string, ReactElement> = {
  energy: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
    </svg>
  ),
  materials: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
      <path d="M12 2l8.66 5v10L12 22l-8.66-5V7z"/>
    </svg>
  ),
  industrials: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
      <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
    </svg>
  ),
  consumer_disc: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
      <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/>
    </svg>
  ),
  consumer_staples: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
    </svg>
  ),
  health_care: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
    </svg>
  ),
  financials: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
      <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>
    </svg>
  ),
  technology: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
      <rect x="2" y="3" width="20" height="14" rx="0"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
    </svg>
  ),
  communication: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
    </svg>
  ),
  utilities: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
      <circle cx="12" cy="12" r="10"/><path d="M8.56 2.75c4.37 6.03 6.02 9.42 8.03 17.72m2.54-15.38c-3.72 4.35-8.94 5.66-16.88 5.85m19.5 1.9c-3.5-.93-6.63-.82-8.94 0-2.58.92-5.01 2.86-7.44 6.32"/>
    </svg>
  ),
  real_estate: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
    </svg>
  ),
  ai_theme: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
      <path d="M12 3L13.5 8.5L19 10L13.5 11.5L12 17L10.5 11.5L5 10L10.5 8.5Z"/>
    </svg>
  ),
}

const DefaultIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
    <circle cx="12" cy="12" r="10"/>
  </svg>
)

// ── Sub-components ─────────────────────────────────────────────────────────────

function SentimentBar({ value }: { value: number | null }) {
  if (value == null) return <div className="h-1 bg-[var(--fd-rule)] w-full" />
  const pct = Math.min(Math.abs(value) * 100, 100)
  const color = value > 0.1 ? 'bg-[var(--color-stock-up)]' : value < -0.1 ? 'bg-[var(--color-stock-down)]' : 'bg-[var(--fd-text-faint)]'
  const label = value > 0.1 ? '+' : value < -0.1 ? '−' : '~'
  return (
    <div className="flex items-center gap-1.5">
      <div className="flex-1 h-1 bg-[var(--fd-rule)] overflow-hidden">
        <div className={clsx('h-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className={clsx('text-[10px] font-semibold w-3 text-right', value > 0.1 ? 'text-[var(--color-stock-up)]' : value < -0.1 ? 'text-[var(--color-stock-down)]' : 'text-[var(--fd-text-faint)]')}>
        {label}
      </span>
    </div>
  )
}

function SectorCard({
  theme,
  onClick,
  selected,
}: {
  theme: SectorTheme
  onClick: () => void
  selected: boolean
}) {
  const { i18n } = useTranslation()
  const isZh = i18n.language === 'zh'
  const displayName = isZh && theme.name_cn ? theme.name_cn : theme.name
  const icon = theme.icon_key ? (SECTOR_ICONS[theme.icon_key] || <DefaultIcon />) : <DefaultIcon />

  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        'flex flex-col gap-3 p-4 border text-left transition-colors w-full',
        selected
          ? 'border-[var(--color-accent)] bg-[var(--fd-bg-elev)]'
          : 'border-border bg-surface-card hover:bg-surface-raised hover:border-[var(--fd-rule-strong)]',
      )}
    >
      {/* Icon + Name */}
      <div className="flex items-start gap-3">
        <span className={clsx('shrink-0 mt-0.5', selected ? 'text-[var(--color-nova)]' : 'text-[#5a8aaa]')}>
          {icon}
        </span>
        <div className="min-w-0">
          <p className={clsx('text-sm font-semibold leading-tight', selected ? 'text-[var(--fd-text-primary)]' : 'text-[var(--fd-text-secondary)]')}>
            {displayName}
          </p>
          {theme.theme_type === 'dynamic_ai' && (
            <span className="text-[9px] font-semibold tracking-widest uppercase text-[var(--color-accent)] mt-0.5 block">AI Theme</span>
          )}
        </div>
      </div>

      {/* Stock count */}
      <p className="text-[10px] text-[var(--fd-text-dim)] font-medium tracking-wider">
        {theme.stock_count.toLocaleString()} stocks
      </p>

      {/* Sentiment bar */}
      <SentimentBar value={theme.avg_sentiment} />

      {/* Top symbols */}
      {theme.top_symbols.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {theme.top_symbols.slice(0, 4).map((sym) => (
            <span key={sym} className="text-[9px] font-semibold tracking-wider text-[#4a7090] bg-[var(--fd-bg)] border border-[var(--fd-rule)] px-1.5 py-0.5">
              {sym}
            </span>
          ))}
        </div>
      )}
    </button>
  )
}

function SectorDetail({ name, themeType }: { name: string; themeType: string }) {
  const { t, i18n } = useTranslation()
  const isZh = i18n.language === 'zh'
  const { data, isLoading } = useSectorThemeDetail(name, themeType)

  if (isLoading) {
    return (
      <div className="border border-border bg-surface-card p-6 animate-pulse space-y-4">
        <div className="h-4 bg-[var(--fd-rule)] w-1/3" />
        <div className="h-3 bg-[var(--fd-rule)] w-2/3" />
        <div className="grid grid-cols-4 gap-2">
          {[1,2,3,4].map(i => <div key={i} className="h-16 bg-[var(--fd-rule)]" />)}
        </div>
      </div>
    )
  }
  if (!data) return null

  const fmtMCap = (v: number | null) => {
    if (!v) return '—'
    if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
    if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
    if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`
    return `$${v.toLocaleString()}`
  }
  const fmtPct = (v: number | null) => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`

  return (
    <div className="border border-[var(--color-accent)]/40 bg-[#071525] space-y-4 p-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-[var(--fd-text-primary)]">
            {isZh && data.name_cn ? data.name_cn : data.name}
          </h2>
          <p className="text-xs text-[var(--fd-text-dim)] mt-1 leading-relaxed max-w-xl">
            {isZh && data.description_cn ? data.description_cn : data.description}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-2xl font-semibold text-[var(--fd-text-primary)]">{data.stock_count.toLocaleString()}</p>
          <p className="text-[10px] text-[var(--fd-text-dim)] uppercase tracking-widest">stocks</p>
        </div>
      </div>

      {/* Top themes */}
      {data.top_themes.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {data.top_themes.slice(0, 6).map((tag) => (
            <span key={tag} className="text-[10px] text-[#7ab0d8] bg-[var(--fd-bg)] border border-[var(--fd-rule)] px-2 py-0.5 font-medium">
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Top stocks grid */}
      {data.stocks.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold tracking-widest uppercase text-[var(--fd-text-dim)] mb-2">
            {t('sectors.topStocks')}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-px bg-[var(--fd-rule)]">
            {data.stocks.slice(0, 10).map((stock) => {
              const pos = stock.change_percent != null && stock.change_percent >= 0
              return (
                <Link
                  key={stock.symbol}
                  to={`/stock/${stock.symbol}`}
                  className="bg-surface-card p-3 hover:bg-surface-raised transition-colors block"
                >
                  <p className="text-xs font-semibold text-[var(--color-nova)]">{stock.symbol}</p>
                  <p className="text-[10px] text-[var(--fd-text-dim)] truncate mt-0.5">
                    {isZh && stock.name_cn ? stock.name_cn : stock.name}
                  </p>
                  {stock.price != null && (
                    <p className="text-xs font-semibold text-[var(--fd-text-primary)] mt-1">
                      ${stock.price.toFixed(2)}
                    </p>
                  )}
                  {stock.change_percent != null && (
                    <p className={clsx('text-[10px] font-semibold', pos ? 'text-[var(--color-stock-up)]' : 'text-[var(--color-stock-down)]')}>
                      {fmtPct(stock.change_percent)}
                    </p>
                  )}
                  <p className="text-[9px] text-[#777] mt-0.5">{fmtMCap(stock.market_cap)}</p>
                </Link>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Sectors() {
  const { t } = useTranslation()
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [selectedType, setSelectedType] = useState<string>('static_gics')

  const { data: themes, isLoading } = useSectorThemes()

  const staticSectors = (themes || []).filter((th) => th.theme_type === 'static_gics')
  const dynamicThemes = (themes || []).filter((th) => th.theme_type === 'dynamic_ai')

  const handleSelect = (name: string, type: string) => {
    if (selectedName === name && selectedType === type) {
      setSelectedName(null)
    } else {
      setSelectedName(name)
      setSelectedType(type)
    }
  }

  return (
    <div className="space-y-8">

      {/* GICS Static Sectors */}
      <section>
        <h2 className="text-sm font-bold tracking-widest uppercase text-[var(--fd-text-secondary)] border-l-2 border-[var(--color-accent)] pl-3 leading-none mb-4">
          {t('sectors.gicsTitle')}
        </h2>

        {isLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-px bg-[var(--fd-rule)] border border-border animate-pulse">
            {Array.from({ length: 11 }).map((_, i) => (
              <div key={i} className="bg-surface-card h-32" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-px bg-[var(--fd-rule)] border border-border">
            {staticSectors.map((theme) => (
              <SectorCard
                key={theme.id}
                theme={theme}
                selected={selectedName === theme.name && selectedType === 'static_gics'}
                onClick={() => handleSelect(theme.name, 'static_gics')}
              />
            ))}
            {/* Filler cell — 11 GICS sectors in a 4-col grid leaves 1 empty slot */}
            {staticSectors.length % 4 !== 0 && (
              <div className="flex flex-col items-center justify-center gap-2 p-4 bg-surface-card border border-dashed border-[#f59e0b]/30 select-none pointer-events-none">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-[#f59e0b]">
                  <circle cx="12" cy="12" r="9" strokeDasharray="3 3"/>
                  <path d="M12 8v4M12 16h.01" strokeWidth="2"/>
                </svg>
                <p className="text-[9px] text-[#f59e0b] text-center leading-tight tracking-widest uppercase font-semibold">
                  Coverage<br/>growing
                </p>
              </div>
            )}
          </div>
        )}
      </section>

      {/* Expanded sector detail */}
      {selectedName && selectedType === 'static_gics' && (
        <SectorDetail name={selectedName} themeType="static_gics" />
      )}

      {/* Dynamic AI Themes */}
      {dynamicThemes.length > 0 && (
        <section>
          <h2 className="text-sm font-bold tracking-widest uppercase text-[var(--fd-text-secondary)] border-l-2 border-[var(--color-accent)] pl-3 leading-none mb-4">
            {t('sectors.trendingThemes')}
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-px bg-[var(--fd-rule)] border border-border">
            {dynamicThemes.map((theme) => (
              <SectorCard
                key={theme.id}
                theme={theme}
                selected={selectedName === theme.name && selectedType === 'dynamic_ai'}
                onClick={() => handleSelect(theme.name, 'dynamic_ai')}
              />
            ))}
          </div>
          {selectedName && selectedType === 'dynamic_ai' && (
            <div className="mt-px">
              <SectorDetail name={selectedName} themeType="dynamic_ai" />
            </div>
          )}
        </section>
      )}

      {/* Empty state if no dynamic themes yet */}
      {!isLoading && dynamicThemes.length === 0 && (
        <section>
          <h2 className="text-sm font-bold tracking-widest uppercase text-[var(--fd-text-secondary)] border-l-2 border-[var(--color-accent)] pl-3 leading-none mb-4">
            {t('sectors.trendingThemes')}
          </h2>
          <p className="text-sm text-[var(--fd-text-faint)] py-4">{t('sectors.noThemesYet')}</p>
        </section>
      )}
    </div>
  )
}
