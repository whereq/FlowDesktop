import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import clsx from 'clsx'
import {
  useIntelligenceNews,
  useIntelligenceSignals,
  useIntelligenceSectors,
} from '../hooks/useStocks'
import type { NewsItem, MarketSignalItem, SectorIntelligenceItem } from '../api/client'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtRelative(iso: string) {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function SentimentPill({ value }: { value: number | null }) {
  if (value == null) return null
  const pos = value > 0.1
  const neg = value < -0.1
  return (
    <span className={clsx(
      'text-[9px] font-semibold px-1.5 py-0.5 border',
      pos ? 'text-[var(--color-stock-up)] border-[var(--color-stock-up)]/30 bg-[#0a1f15]'
          : neg ? 'text-[var(--color-stock-down)] border-[var(--color-stock-down)]/30 bg-[#1a0808]'
          : 'text-[var(--fd-text-faint)] border-[var(--fd-rule)] bg-[#111]'
    )}>
      {value >= 0 ? '+' : ''}{value.toFixed(2)}
    </span>
  )
}

function SourceBadge({ source }: { source: string }) {
  const colors: Record<string, string> = {
    polygon: 'text-[var(--color-nova)] bg-[var(--color-nova)]/10 border-[var(--color-nova)]/30',
    eastmoney: 'text-[#f59e0b] bg-[#f59e0b]/10 border-[#f59e0b]/30',
    sina: 'text-[#f59e0b] bg-[#f59e0b]/10 border-[#f59e0b]/30',
    reddit: 'text-[#ff6b35] bg-[#ff6b35]/10 border-[#ff6b35]/30',
    sec_edgar: 'text-[#a78bfa] bg-[#a78bfa]/10 border-[#a78bfa]/30',
  }
  return (
    <span className={clsx('text-[9px] font-semibold px-1.5 py-0.5 border uppercase tracking-wider', colors[source] || 'text-[var(--fd-text-faint)] border-[var(--fd-rule)] bg-[#111]')}>
      {source.replace('_', ' ')}
    </span>
  )
}

function SignalTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    earnings: 'text-[var(--color-stock-up)] border-[var(--color-stock-up)]/30 bg-[#0a1f15]',
    macro: 'text-[var(--color-accent)] border-[var(--color-accent)]/30 bg-[#071525]',
    geopolitical: 'text-[var(--color-stock-down)] border-[var(--color-stock-down)]/30 bg-[#1a0808]',
    sector: 'text-[#f59e0b] border-[#f59e0b]/30 bg-[#1a1000]',
    regulatory: 'text-[#a78bfa] border-[#a78bfa]/30 bg-[#120f20]',
    corporate: 'text-[var(--fd-text-secondary)] border-[var(--fd-rule)] bg-[#111]',
  }
  return (
    <span className={clsx('text-[9px] font-semibold px-1.5 py-0.5 border uppercase tracking-wider', colors[type] || 'text-[var(--fd-text-faint)] border-[var(--fd-rule)] bg-[#111]')}>
      {type}
    </span>
  )
}

function SentimentBar({ value }: { value: number | null }) {
  if (value == null) return <div className="h-1 bg-[var(--fd-rule)] w-full" />
  const pct = Math.min(Math.abs(value) * 100, 100)
  const color = value > 0.1 ? 'bg-[var(--color-stock-up)]' : value < -0.1 ? 'bg-[var(--color-stock-down)]' : 'bg-[#555]'
  return (
    <div className="h-1 bg-[var(--fd-rule)] w-full overflow-hidden">
      <div className={clsx('h-full', color)} style={{ width: `${pct}%` }} />
    </div>
  )
}

// ── Filters ───────────────────────────────────────────────────────────────────

const HOURS_OPTIONS = [
  { value: 4,   label: '4h' },
  { value: 24,  label: '24h' },
  { value: 48,  label: '48h' },
  { value: 168, label: '7d' },
]

const SOURCES = ['polygon', 'eastmoney', 'sina', 'reddit', 'sec_edgar']
const REGIONS = ['US', 'CN', 'HK', 'GLOBAL']
const SIGNAL_TYPES = ['earnings', 'macro', 'geopolitical', 'sector', 'regulatory', 'corporate']

function FilterPill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        'px-2.5 py-1 text-[10px] font-semibold border uppercase tracking-wider transition-colors',
        active
          ? 'border-[var(--color-accent)] bg-[var(--fd-bg-elev)] text-[var(--color-nova)]'
          : 'border-[var(--fd-rule)] bg-[var(--fd-bg)] text-[var(--fd-text-faint)] hover:text-[var(--fd-text-dim)] hover:border-[var(--fd-rule-strong)]'
      )}
    >
      {label}
    </button>
  )
}

// ── News Tab ──────────────────────────────────────────────────────────────────

function NewsTab() {
  const { i18n } = useTranslation()
  const [hours, setHours] = useState(24)
  const [source, setSource] = useState<string | undefined>()
  const [region, setRegion] = useState<string | undefined>()
  const [language, setLanguage] = useState<string | undefined>()

  const { data: items = [], isLoading } = useIntelligenceNews({ hours, source, region, language, limit: 100 })

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="flex gap-1">
          {HOURS_OPTIONS.map(o => (
            <FilterPill key={o.value} label={o.label} active={hours === o.value} onClick={() => setHours(o.value)} />
          ))}
        </div>
        <div className="w-px h-4 bg-[var(--fd-rule)]" />
        <FilterPill label="All Sources" active={!source} onClick={() => setSource(undefined)} />
        {SOURCES.map(s => (
          <FilterPill key={s} label={s.replace('_', ' ')} active={source === s} onClick={() => setSource(source === s ? undefined : s)} />
        ))}
        <div className="w-px h-4 bg-[var(--fd-rule)]" />
        <FilterPill label="All Regions" active={!region} onClick={() => setRegion(undefined)} />
        {REGIONS.map(r => (
          <FilterPill key={r} label={r} active={region === r} onClick={() => setRegion(region === r ? undefined : r)} />
        ))}
        <div className="w-px h-4 bg-[var(--fd-rule)]" />
        <FilterPill label="EN" active={language === 'en'} onClick={() => setLanguage(language === 'en' ? undefined : 'en')} />
        <FilterPill label="ZH" active={language === 'zh'} onClick={() => setLanguage(language === 'zh' ? undefined : 'zh')} />
      </div>

      {/* Count */}
      <p className="text-[10px] text-[var(--fd-text-dim)]">{items.length} articles</p>

      {/* Loading */}
      {isLoading && (
        <div className="space-y-px">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-16 bg-surface-card border border-border animate-pulse" />
          ))}
        </div>
      )}

      {/* Empty */}
      {!isLoading && items.length === 0 && (
        <p className="text-sm text-[var(--fd-text-dim)] py-8 text-center">No news articles found. Collection runs every 30 minutes.</p>
      )}

      {/* Items */}
      {!isLoading && items.length > 0 && (
        <div className="border border-border bg-surface-card overflow-hidden">
          {items.map((item, i) => (
            <NewsRow key={item.id} item={item} last={i === items.length - 1} lang={i18n.language} />
          ))}
        </div>
      )}
    </div>
  )
}

function NewsRow({ item, last }: { item: NewsItem; last: boolean; lang?: string }) {
  return (
    <div className={clsx('flex items-start gap-3 px-4 py-3 hover:bg-surface-raised transition-colors', !last && 'border-b border-[#111]')}>
      <div className="flex-1 min-w-0 space-y-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          <SourceBadge source={item.source} />
          {item.region && (
            <span className="text-[9px] text-[#777] border border-[var(--fd-rule)] px-1.5 py-0.5">{item.region}</span>
          )}
          <span className="text-[10px] text-[#666]">{fmtRelative(item.published_at)}</span>
          {item.raw_sentiment != null && <SentimentPill value={item.raw_sentiment} />}
          {!item.is_processed && (
            <span className="text-[9px] text-[#777] border border-[var(--fd-rule)] px-1.5 py-0.5">unprocessed</span>
          )}
        </div>
        {item.url ? (
          <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-sm text-[var(--fd-text-secondary)] hover:text-[var(--fd-text-primary)] transition-colors leading-snug block">
            {item.title}
          </a>
        ) : (
          <p className="text-sm text-[var(--fd-text-secondary)] leading-snug">{item.title}</p>
        )}
        {item.summary && (
          <p className="text-[10px] text-[var(--fd-text-dim)] leading-relaxed line-clamp-2">{item.summary}</p>
        )}
      </div>
    </div>
  )
}

// ── Signals Tab ───────────────────────────────────────────────────────────────

function SignalsTab() {
  const { i18n } = useTranslation()
  const isZh = i18n.language === 'zh'
  const [hours, setHours] = useState(24)
  const [signalType, setSignalType] = useState<string | undefined>()

  const { data: items = [], isLoading } = useIntelligenceSignals({ hours, signal_type: signalType, limit: 100 })

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="flex gap-1">
          {HOURS_OPTIONS.map(o => (
            <FilterPill key={o.value} label={o.label} active={hours === o.value} onClick={() => setHours(o.value)} />
          ))}
        </div>
        <div className="w-px h-4 bg-[var(--fd-rule)]" />
        <FilterPill label="All Types" active={!signalType} onClick={() => setSignalType(undefined)} />
        {SIGNAL_TYPES.map(t => (
          <FilterPill key={t} label={t} active={signalType === t} onClick={() => setSignalType(signalType === t ? undefined : t)} />
        ))}
      </div>

      <p className="text-[10px] text-[var(--fd-text-dim)]">{items.length} signals</p>

      {isLoading && (
        <div className="space-y-px">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 bg-surface-card border border-border animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && items.length === 0 && (
        <p className="text-sm text-[var(--fd-text-dim)] py-8 text-center">No signals yet. Processing runs hourly after news collection.</p>
      )}

      {!isLoading && items.length > 0 && (
        <div className="border border-border bg-surface-card overflow-hidden">
          {items.map((sig, i) => (
            <SignalRow key={sig.id} sig={sig} last={i === items.length - 1} isZh={isZh} />
          ))}
        </div>
      )}
    </div>
  )
}

function SignalRow({ sig, last, isZh }: { sig: MarketSignalItem; last: boolean; isZh: boolean }) {
  const summary = (isZh ? sig.summary_zh : sig.summary_en) || sig.summary_en || sig.summary_zh
  return (
    <div className={clsx('px-4 py-3 hover:bg-surface-raised transition-colors space-y-2', !last && 'border-b border-[#111]')}>
      <div className="flex items-center gap-2 flex-wrap">
        <SignalTypeBadge type={sig.signal_type} />
        <SentimentPill value={sig.sentiment} />
        {sig.confidence != null && (
          <span className="text-[9px] text-[#777] border border-[var(--fd-rule)] px-1.5 py-0.5">
            conf {(sig.confidence * 100).toFixed(0)}%
          </span>
        )}
        {sig.impact_horizon && (
          <span className="text-[9px] text-[#777] border border-[var(--fd-rule)] px-1.5 py-0.5">{sig.impact_horizon}</span>
        )}
        <span className="text-[10px] text-[#666] ml-auto">{fmtRelative(sig.processed_at)}</span>
      </div>

      {/* Sentiment bar */}
      <SentimentBar value={sig.sentiment} />

      {/* Summary */}
      {summary && <p className="text-sm text-[var(--fd-text-secondary)] leading-snug">{summary}</p>}

      {/* Tags row */}
      <div className="flex flex-wrap gap-1.5">
        {sig.regions.map(r => (
          <span key={r} className="text-[9px] text-[#4a7090] border border-[var(--fd-rule)] px-1.5 py-0.5">{r}</span>
        ))}
        {sig.sectors_affected.slice(0, 3).map(s => (
          <span key={s} className="text-[9px] text-[#7ab0d8] border border-[var(--fd-rule)] px-1.5 py-0.5">{s}</span>
        ))}
        {sig.theme_tags.slice(0, 4).map(t => (
          <span key={t} className="text-[9px] text-[#a78bfa] border border-[var(--fd-rule)] px-1.5 py-0.5">{t}</span>
        ))}
      </div>

      {/* Symbols */}
      {(sig.symbols_mentioned.length > 0 || sig.symbols_impacted.length > 0) && (
        <div className="flex flex-wrap gap-1">
          {sig.symbols_mentioned.slice(0, 6).map(sym => (
            <Link key={sym} to={`/stock/${sym}`} className="text-[9px] font-semibold text-[var(--color-nova)] bg-[#071525] border border-[var(--color-accent)]/30 px-1.5 py-0.5 hover:border-[var(--color-nova)] transition-colors">
              {sym}
            </Link>
          ))}
          {sig.symbols_impacted.slice(0, 4).map((sym) => (
            <Link key={sym} to={`/stock/${sym}`} className="text-[9px] font-semibold text-[var(--fd-text-dim)] bg-[#111] border border-[var(--fd-rule)] px-1.5 py-0.5 hover:border-[var(--fd-text-faint)] transition-colors">
              {sym}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Sectors Tab ───────────────────────────────────────────────────────────────

const SECTOR_REGIONS = ['US', 'CN', 'HK', 'GLOBAL']

function SectorsTab() {
  const { i18n } = useTranslation()
  const isZh = i18n.language === 'zh'
  const [region, setRegion] = useState<string | undefined>('US')
  const [expanded, setExpanded] = useState<number | null>(null)

  const { data: items = [], isLoading } = useIntelligenceSectors({ region })

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <FilterPill label="All Regions" active={!region} onClick={() => setRegion(undefined)} />
        {SECTOR_REGIONS.map(r => (
          <FilterPill key={r} label={r} active={region === r} onClick={() => setRegion(region === r ? undefined : r)} />
        ))}
      </div>

      {isLoading && (
        <div className="space-y-px">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-20 bg-surface-card border border-border animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && items.length === 0 && (
        <p className="text-sm text-[var(--fd-text-dim)] py-8 text-center">
          No sector intelligence yet. Aggregation runs daily at 23:00 UTC after signals are processed.
        </p>
      )}

      {!isLoading && items.length > 0 && (
        <div className="border border-border bg-surface-card overflow-hidden">
          {items.map((item, i) => (
            <SectorIntelRow
              key={item.id}
              item={item}
              last={i === items.length - 1}
              isZh={isZh}
              expanded={expanded === item.id}
              onToggle={() => setExpanded(expanded === item.id ? null : item.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function SectorIntelRow({ item, last, expanded, onToggle }: {
  item: SectorIntelligenceItem; last: boolean; isZh?: boolean; expanded: boolean; onToggle: () => void
}) {
  return (
    <div className={clsx(!last && 'border-b border-[#111]')}>
      <button
        type="button"
        onClick={onToggle}
        className="w-full px-4 py-3 hover:bg-surface-raised transition-colors text-left space-y-2"
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-[var(--fd-text-primary)]">{item.sector}</span>
          <span className="text-[9px] text-[#777] border border-[var(--fd-rule)] px-1.5 py-0.5">{item.region}</span>
          <SentimentPill value={item.avg_sentiment} />
          <span className="text-[10px] text-[var(--fd-text-dim)] ml-auto">
            {item.signal_count} signals · {item.bullish_count}↑ {item.bearish_count}↓
          </span>
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="#5a8aaa" strokeWidth="2.5" strokeLinecap="square"
            style={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s', flexShrink: 0 }}>
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </div>
        <SentimentBar value={item.avg_sentiment} />
        {item.top_themes.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.top_themes.slice(0, 5).map(t => (
              <span key={t} className="text-[9px] text-[#a78bfa] border border-[var(--fd-rule)] px-1.5 py-0.5">{t}</span>
            ))}
          </div>
        )}
      </button>
      {expanded && item.narrative && (
        <div className="px-4 pb-4 border-t border-[var(--fd-bg)]">
          <p className="text-xs text-[var(--fd-text-dim)] leading-relaxed mt-3 whitespace-pre-wrap">{item.narrative}</p>
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = 'news' | 'signals' | 'sectors'

export default function Intelligence() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<Tab>('news')

  const tabs: { key: Tab; label: string }[] = [
    { key: 'news',    label: t('intel.tabNews') },
    { key: 'signals', label: t('intel.tabSignals') },
    { key: 'sectors', label: t('intel.tabSectors') },
  ]

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-lg font-bold text-[var(--fd-text-primary)] tracking-tight">{t('intel.title')}</h1>
        <p className="text-xs text-[var(--fd-text-dim)] mt-0.5">{t('intel.subtitle')}</p>
      </div>

      {/* Tab bar */}
      <div className="flex bg-[var(--fd-bg-elevated)] p-px border border-border">
        {tabs.map(tab => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={clsx(
              'flex-1 py-2 text-xs font-semibold tracking-wider uppercase transition-colors',
              activeTab === tab.key
                ? 'bg-[var(--color-accent)] text-white'
                : 'text-[var(--fd-text-faint)] hover:text-[var(--fd-text-dim)] hover:bg-[#111]'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'news'    && <NewsTab />}
      {activeTab === 'signals' && <SignalsTab />}
      {activeTab === 'sectors' && <SectorsTab />}
    </div>
  )
}
