/**
 * AdminDashboard — fd-admin only collector monitoring page.
 *
 * Sections:
 *   1. Summary stats (6 KPIs)
 *   2. Potential Issues / Anomalies (auto-detected)
 *   3. Active Blockers
 *   4. Coverage History Heatmap (exchanges × dates, multi-day view)
 *   5. Per-provider performance + quota
 *   6. Per-exchange today's coverage + historical freshness
 *   7. Scheduled job runs
 *   8. Coverage gaps by exchange
 */
import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import clsx from 'clsx'
import { useAdminStatus, useAdminHistory, useAdminAnomalies } from '../hooks/useStocks'

// ── Time helpers ──────────────────────────────────────────────────────────────

function normalizeUtc(iso: string): string {
  const hasTz = iso.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(iso)
  return hasTz ? iso : iso + 'Z'
}

function fmtRelative(iso: string | null): string {
  if (!iso) return '—'
  const diff = Math.floor((Date.now() - new Date(normalizeUtc(iso)).getTime()) / 1000)
  if (diff <= 0) return 'just now'
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) { const m = Math.floor(diff / 60), s = diff % 60; return `${m}m ${s}s ago` }
  if (diff < 86400) { const h = Math.floor(diff / 3600), m = Math.floor((diff % 3600) / 60); return `${h}h ${m}m ago` }
  const d = Math.floor(diff / 86400), h = Math.floor((diff % 86400) / 3600)
  return `${d}d ${h}h ago`
}

function fmtTime(iso: string | null, locale: string): string {
  if (!iso) return '—'
  return new Date(normalizeUtc(iso)).toLocaleString(locale, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function fmtNum(n: number, locale: string): string {
  return n.toLocaleString(locale)
}

// ── Date range helpers ────────────────────────────────────────────────────────

function dateOffset(base: string, days: number): string {
  const d = new Date(base)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function generateDateRange(start: string, end: string): string[] {
  const dates: string[] = []
  let cur = start
  while (cur <= end) {
    dates.push(cur)
    cur = dateOffset(cur, 1)
  }
  return dates
}

// ── Shared UI ─────────────────────────────────────────────────────────────────

function SectionHeading({ label, badge }: { label: string; badge?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 mb-3">
      <h2 className="text-sm font-bold tracking-widest uppercase text-[var(--fd-text-secondary)] border-l-2 border-[var(--color-accent)] pl-3 leading-none">
        {label}
      </h2>
      {badge}
    </div>
  )
}

function StatCard({ label, value, sub, accent }: {
  label: string; value: string | number; sub?: string
  accent?: 'green' | 'amber' | 'red' | 'cyan' | 'default'
}) {
  const color = {
    green: 'text-[var(--color-stock-up)]', amber: 'text-[#f59e0b]',
    red: 'text-[var(--color-stock-down)]', cyan: 'text-[var(--color-nova)]', default: 'text-[var(--fd-text-primary)]',
  }[accent ?? 'cyan']
  return (
    <div className="bg-[var(--fd-bg)] border border-[var(--fd-rule)] p-4 flex flex-col gap-1">
      <p className="text-[10px] font-semibold tracking-widest uppercase text-[#a8b4c4]">{label}</p>
      <p className={clsx('text-xl font-semibold leading-tight', color)}>{value}</p>
      {sub && <p className="text-[10px] text-[#8899aa]">{sub}</p>}
    </div>
  )
}

function StatusDot({ status }: { status: string }) {
  const cls =
    status === 'completed' || status === 'ok' ? 'bg-[var(--color-stock-up)]'
    : status === 'failed' ? 'bg-[var(--color-stock-down)]'
    : status === 'running' ? 'bg-[#f59e0b] animate-pulse'
    : 'bg-[var(--fd-text-faint)]'
  return <span className={clsx('inline-block w-2 h-2 rounded-full shrink-0', cls)} />
}

function CoverageBar({ pct }: { pct: number }) {
  const color = pct >= 80 ? 'bg-[var(--color-stock-up)]' : pct >= 50 ? 'bg-[#f59e0b]' : pct > 0 ? 'bg-[var(--color-stock-down)]' : 'bg-[var(--fd-rule)]'
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="flex-1 h-1.5 bg-[var(--fd-rule)] rounded-sm overflow-hidden">
        <div className={clsx('h-full rounded-sm transition-all', color)} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="text-xs text-[var(--fd-text-dim)] w-10 text-right tabular-nums shrink-0">{pct.toFixed(1)}%</span>
    </div>
  )
}

function QuotaBar({ used, limit }: { used: number; limit: number | null }) {
  if (!limit) return <span className="text-xs text-[#8899aa]">—</span>
  const pct = Math.min((used / limit) * 100, 100)
  const color = pct >= 95 ? 'bg-[var(--color-stock-down)]' : pct >= 70 ? 'bg-[#f59e0b]' : 'bg-[var(--color-stock-up)]'
  return (
    <div className="flex items-center gap-1.5 min-w-0">
      <div className="flex-1 h-1 bg-[var(--fd-rule)] rounded-sm overflow-hidden">
        <div className={clsx('h-full rounded-sm', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-[#a8b4c4] tabular-nums shrink-0 whitespace-nowrap">
        {used.toLocaleString()}/{limit.toLocaleString()}
      </span>
    </div>
  )
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <th className={clsx(
      'px-3 py-2 text-[10px] font-semibold tracking-widest uppercase text-[#a8b4c4] bg-[#070f1a] border-b border-[var(--fd-rule)] whitespace-nowrap',
      right ? 'text-right' : 'text-left'
    )}>{children}</th>
  )
}

function Td({ children, right, mono, muted, className }: {
  children: React.ReactNode; right?: boolean; mono?: boolean; muted?: boolean; className?: string
}) {
  return (
    <td className={clsx(
      'px-3 py-2 text-xs border-b border-[#0d1520]',
      right ? 'text-right' : 'text-left',
      mono ? 'font-mono' : '',
      muted ? 'text-[#666]' : 'text-[var(--fd-text-secondary)]',
      className,
    )}>{children}</td>
  )
}

// ── Heatmap cell ──────────────────────────────────────────────────────────────

function HeatCell({ pct, title }: { pct: number | null; title: string }) {
  if (pct === null) {
    return (
      <td title={title} className="w-8 h-7 border border-[#0a1015] bg-[#0d0d0d]" />
    )
  }
  const bg =
    pct >= 90 ? 'bg-[#064e3b]'
    : pct >= 70 ? 'bg-[#065f46]'
    : pct >= 50 ? 'bg-[#854d0e]'
    : pct >= 20 ? 'bg-[#7f1d1d]'
    : pct > 0   ? 'bg-[#450a0a]'
    : 'bg-[#111827]'
  const text =
    pct >= 70 ? 'text-[#6ee7b7]'
    : pct >= 50 ? 'text-[#fcd34d]'
    : pct > 0  ? 'text-[#fca5a5]'
    : 'text-[#374151]'
  return (
    <td
      title={title}
      className={clsx('w-8 h-7 text-center border border-[#0a1015] cursor-default transition-opacity hover:opacity-80', bg)}
    >
      <span className={clsx('text-[9px] font-mono tabular-nums leading-none', text)}>
        {pct === 0 ? '0' : pct < 10 ? pct.toFixed(0) : pct.toFixed(0)}
      </span>
    </td>
  )
}

// ── Anomaly row ───────────────────────────────────────────────────────────────

function AnomalyRow({ anomaly }: { anomaly: { severity: string; title: string; detail: string; exchange: string | null; provider: string | null; type: string } }) {
  const sev = anomaly.severity
  const colors = sev === 'critical'
    ? { bg: 'bg-[#1a0808]', dot: 'bg-[var(--color-stock-down)]', text: 'text-[#fca5a5]', badge: 'bg-[var(--color-stock-down)]/20 text-[var(--color-stock-down)]' }
    : sev === 'warning'
    ? { bg: 'bg-[#0f1a0a]', dot: 'bg-[#f59e0b]', text: 'text-[#fcd34d]', badge: 'bg-[#f59e0b]/20 text-[#f59e0b]' }
    : { bg: 'bg-[var(--fd-bg)]', dot: 'bg-[#60a5fa]', text: 'text-[#93c5fd]', badge: 'bg-[#60a5fa]/20 text-[#60a5fa]' }
  return (
    <div className={clsx('flex items-start gap-3 px-4 py-3 border-b border-[#0d1520] last:border-0', colors.bg)}>
      <span className={clsx('mt-0.5 w-2 h-2 rounded-full shrink-0', colors.dot)} />
      <div className="flex-1 min-w-0">
        <p className={clsx('text-xs font-semibold', colors.text)}>{anomaly.title}</p>
        <p className="text-[10px] text-[#666] mt-0.5">{anomaly.detail}</p>
      </div>
      <span className={clsx('shrink-0 text-[9px] font-semibold px-1.5 py-0.5 uppercase tracking-wider', colors.badge)}>
        {anomaly.severity}
      </span>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const { t, i18n } = useTranslation()
  const locale = i18n.language.startsWith('zh') ? 'zh-CN' : 'en-US'

  const today = new Date().toISOString().slice(0, 10)
  const [refDate, setRefDate] = useState(today)

  // History range
  const [histPreset, setHistPreset] = useState<7 | 14 | 30>(14)
  const [histExchange, setHistExchange] = useState<string>('')
  const histEnd = today
  const histStart = dateOffset(today, -histPreset + 1)

  const { data, isLoading, error, refetch, dataUpdatedAt } = useAdminStatus(refDate)
  const { data: histData, isLoading: histLoading } = useAdminHistory(histStart, histEnd, histExchange || undefined)
  const { data: anomData, isLoading: anomLoading } = useAdminAnomalies(14)

  // Build heatmap: exchange → date → pct
  const { heatDates, heatExchanges, heatMap } = useMemo(() => {
    const dates = generateDateRange(histStart, histEnd)
    const exchangeSet = new Set<string>()
    const map: Record<string, Record<string, number>> = {}

    if (histData) {
      for (const row of histData.data) {
        exchangeSet.add(row.exchange)
        if (!map[row.exchange]) map[row.exchange] = {}
        map[row.exchange][row.date] = row.coverage_pct
      }
    }
    const exchanges = Array.from(exchangeSet).sort()
    return { heatDates: dates, heatExchanges: exchanges, heatMap: map }
  }, [histData, histStart, histEnd])

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        {[1, 2, 3, 4].map(i => <div key={i} className="h-28 bg-[var(--fd-bg)] border border-[var(--fd-rule)]" />)}
      </div>
    )
  }

  if (error || !data) {
    return <div className="border border-[#ef4444]/40 bg-[#1a0808] p-6 text-[var(--color-stock-down)] text-sm">{t('admin.loadError')}</div>
  }

  const { summary, providers, exchanges, jobs, blockers, gaps } = data
  const coverageAccent = summary.coverage_rate >= 80 ? 'green' : summary.coverage_rate >= 50 ? 'amber' : 'red'

  // Anomaly badge for section heading
  const critCount = anomData?.critical_count ?? 0
  const warnCount = anomData?.warning_count ?? 0
  const infoCount = anomData ? (anomData.anomaly_count - critCount - warnCount) : 0
  const anomalyBadge = critCount > 0
    ? <span className="text-[10px] font-bold px-1.5 py-0.5 bg-[var(--color-stock-down)]/20 text-[var(--color-stock-down)]">{critCount} critical</span>
    : warnCount > 0
    ? <span className="text-[10px] font-bold px-1.5 py-0.5 bg-[#f59e0b]/20 text-[#f59e0b]">{warnCount} warning</span>
    : infoCount > 0
    ? <span className="text-[10px] font-bold px-1.5 py-0.5 bg-[#60a5fa]/20 text-[#60a5fa]">{infoCount} info</span>
    : null

  return (
    <div className="space-y-8">

      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold text-[var(--fd-text-primary)] tracking-tight">{t('admin.title')}</h1>
          <p className="text-xs text-[#8899aa] mt-0.5">
            {t('admin.subtitle')}
            {dataUpdatedAt && <> · {t('status.fetched')} {fmtRelative(new Date(dataUpdatedAt).toISOString())}</>}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <label className="text-[10px] text-[#8899aa] uppercase tracking-wider">{t('admin.dateRange')}</label>
          <input
            type="date"
            value={refDate}
            max={today}
            onChange={e => setRefDate(e.target.value)}
            className="text-xs bg-[var(--fd-bg)] border border-[var(--fd-rule)] text-[var(--fd-text-secondary)] px-2 py-1 focus:outline-none focus:border-[var(--color-accent)]"
          />
          <button
            onClick={() => refetch()}
            className="text-xs px-3 py-1 border border-[var(--color-accent)]/50 text-[var(--color-nova)] hover:bg-[var(--color-accent)]/10 transition-colors"
          >
            {t('admin.refresh')}
          </button>
        </div>
      </div>

      {/* ── Summary stats ── */}
      <section>
        <SectionHeading label={t('admin.sectionSummary')} />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-px bg-[var(--fd-rule)] border border-[var(--fd-rule)]">
          <StatCard label={t('admin.totalStocks')} value={fmtNum(summary.total_active_stocks, locale)} accent="cyan" />
          <StatCard label={t('admin.quotedToday')} value={fmtNum(summary.quoted_today, locale)} accent="cyan" />
          <StatCard label={t('admin.coverageRate')} value={`${summary.coverage_rate.toFixed(1)}%`} accent={coverageAccent as 'green' | 'amber' | 'red'} />
          <StatCard label={t('admin.historicalRecords')} value={fmtNum(summary.total_historical_db, locale)} accent="cyan" />
          <StatCard label={t('admin.totalQuotesDb')} value={fmtNum(summary.total_quotes_db, locale)} accent="cyan" />
          <StatCard label={t('admin.lastActivity')} value={fmtRelative(summary.last_activity)} sub={fmtTime(summary.last_activity, locale)} />
        </div>
      </section>

      {/* ── Anomalies ── */}
      <section>
        <SectionHeading label={t('admin.sectionAnomalies')} badge={anomalyBadge} />
        {anomLoading ? (
          <div className="h-12 bg-[var(--fd-bg)] border border-[var(--fd-rule)] animate-pulse" />
        ) : !anomData || anomData.anomalies.length === 0 ? (
          <div className="flex items-center gap-2 px-4 py-3 bg-[#0a1f15] border border-[#10b981]/20 text-[var(--color-stock-up)] text-xs">
            <span className="w-2 h-2 rounded-full bg-[var(--color-stock-up)]" />{t('admin.noAnomalies')}
          </div>
        ) : (
          <div className="border border-[var(--fd-rule)] bg-[#0a1015]">
            {anomData.anomalies.map((a, i) => <AnomalyRow key={i} anomaly={a} />)}
          </div>
        )}
      </section>

      {/* ── Active blockers ── */}
      <section>
        <SectionHeading label={t('admin.sectionBlockers')} />
        {blockers.length === 0 ? (
          <div className="flex items-center gap-2 px-4 py-3 bg-[#0a1f15] border border-[#10b981]/20 text-[var(--color-stock-up)] text-xs">
            <span className="w-2 h-2 rounded-full bg-[var(--color-stock-up)]" />{t('admin.noBlockers')}
          </div>
        ) : (
          <div className="space-y-1.5">
            {blockers.map((b, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-3 bg-[#1a0808] border border-[#ef4444]/20 text-xs">
                <span className="w-2 h-2 rounded-full bg-[var(--color-stock-down)] shrink-0" />
                <span className="font-mono font-semibold text-[#f3a3a3]">{b.provider}</span>
                <span className="text-[#a8b4c4] uppercase tracking-wider text-[10px]">{b.type.replace(/_/g, ' ')}</span>
                <span className="text-[var(--color-stock-down)]">{b.message}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Coverage History Heatmap ── */}
      <section>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-3">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-bold tracking-widest uppercase text-[var(--fd-text-secondary)] border-l-2 border-[var(--color-accent)] pl-3 leading-none">
              {t('admin.sectionHistory')}
            </h2>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* Preset buttons */}
            {([7, 14, 30] as const).map(n => (
              <button
                key={n}
                onClick={() => setHistPreset(n)}
                className={clsx(
                  'text-[10px] px-2 py-1 border transition-colors',
                  histPreset === n
                    ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/20 text-[var(--color-nova)]'
                    : 'border-[var(--fd-rule)] text-[#8899aa] hover:text-[var(--fd-text-dim)] hover:border-[var(--fd-rule-strong)]'
                )}
              >
                {n === 7 ? t('admin.historyPreset7') : n === 14 ? t('admin.historyPreset14') : t('admin.historyPreset30')}
              </button>
            ))}
            {/* Exchange filter */}
            <select
              value={histExchange}
              onChange={e => setHistExchange(e.target.value)}
              className="text-[10px] bg-[var(--fd-bg)] border border-[var(--fd-rule)] text-[var(--fd-text-secondary)] px-2 py-1 focus:outline-none focus:border-[var(--color-accent)]"
            >
              <option value="">{t('admin.historyAllExchanges')}</option>
              {data.exchanges.map(ex => (
                <option key={ex.exchange} value={ex.exchange}>{ex.exchange}</option>
              ))}
            </select>
          </div>
        </div>

        {histLoading ? (
          <div className="h-32 bg-[var(--fd-bg)] border border-[var(--fd-rule)] animate-pulse" />
        ) : heatExchanges.length === 0 ? (
          <div className="px-4 py-6 text-center text-xs text-[#8899aa] border border-[var(--fd-rule)]">{t('admin.noHistory')}</div>
        ) : (
          <div className="overflow-x-auto border border-[var(--fd-rule)]">
            <table className="border-collapse text-left" style={{ tableLayout: 'auto' }}>
              <thead>
                <tr>
                  <th className="px-3 py-1.5 text-[10px] font-semibold tracking-widest uppercase text-[#a8b4c4] bg-[#070f1a] border-b border-r border-[var(--fd-rule)] whitespace-nowrap sticky left-0 z-10">
                    {t('admin.colExchange')}
                  </th>
                  {heatDates.map(d => (
                    <th key={d} className="w-8 text-center text-[8px] text-[#8899aa] bg-[#070f1a] border-b border-[var(--fd-rule)] pb-1 pt-1.5 font-normal">
                      {d.slice(5)} {/* MM-DD */}
                    </th>
                  ))}
                  <th className="px-3 py-1.5 text-[10px] font-semibold tracking-widest uppercase text-[#a8b4c4] bg-[#070f1a] border-b border-l border-[var(--fd-rule)] whitespace-nowrap">
                    {t('admin.colCoverage')} avg
                  </th>
                </tr>
              </thead>
              <tbody>
                {heatExchanges.map(ex => {
                  const exRow = data.exchanges.find(e => e.exchange === ex)
                  const dayValues = heatDates.map(d => heatMap[ex]?.[d] ?? null)
                  const definedVals = dayValues.filter((v): v is number => v !== null)
                  const avg = definedVals.length ? definedVals.reduce((a, b) => a + b, 0) / definedVals.length : 0
                  return (
                    <tr key={ex} className="hover:brightness-125 transition-all">
                      <td className="px-3 py-0 text-xs font-mono text-[var(--fd-text-secondary)] bg-[#0a1015] border-r border-b border-[#0d1520] sticky left-0 z-10 whitespace-nowrap">
                        {ex}
                      </td>
                      {heatDates.map((d, di) => {
                        const pct = heatMap[ex]?.[d] ?? null
                        const total = exRow?.total ?? 0
                        const quoted = pct !== null ? Math.round(pct * total / 100) : 0
                        const title = pct !== null
                          ? t('admin.historyCellTitle', { exchange: ex, date: d, pct: pct.toFixed(1), quoted, total })
                          : `${ex} on ${d}: no data`
                        return <HeatCell key={di} pct={pct} title={title} />
                      })}
                      <td className="px-3 py-0 text-xs text-right tabular-nums text-[var(--fd-text-dim)] bg-[#0a1015] border-l border-b border-[#0d1520]">
                        <span className={clsx(
                          avg >= 80 ? 'text-[var(--color-stock-up)]' : avg >= 50 ? 'text-[#f59e0b]' : avg > 0 ? 'text-[var(--color-stock-down)]' : 'text-[#444]'
                        )}>
                          {avg > 0 ? `${avg.toFixed(1)}%` : '—'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {/* Legend */}
            <div className="flex items-center gap-4 px-3 py-2 bg-[#070f1a] border-t border-[var(--fd-rule)]">
              <span className="text-[9px] text-[#8899aa] uppercase tracking-wider">Coverage:</span>
              {[['≥90%','bg-[#064e3b] text-[#6ee7b7]'],['≥70%','bg-[#065f46] text-[#6ee7b7]'],['≥50%','bg-[#854d0e] text-[#fcd34d]'],['≥20%','bg-[#7f1d1d] text-[#fca5a5]'],['>0%','bg-[#450a0a] text-[#fca5a5]'],['0%','bg-[#111827] text-[#374151]']].map(([label, cls]) => (
                <span key={label} className="flex items-center gap-1">
                  <span className={clsx('w-4 h-3 text-[8px] flex items-center justify-center font-mono', cls)}>{label.slice(1, 3)}</span>
                  <span className="text-[9px] text-[#8899aa]">{label}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ── Provider performance ── */}
      <section>
        <SectionHeading label={t('admin.sectionProviders')} />
        {providers.length === 0 ? (
          <p className="text-xs text-[#8899aa] py-4">{t('admin.noProviders')}</p>
        ) : (
          <div className="overflow-x-auto border border-[var(--fd-rule)]">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr>
                  <Th>{t('admin.colProvider')}</Th>
                  <Th right>{t('admin.colAttempted')}</Th>
                  <Th right>{t('admin.colSucceeded')}</Th>
                  <Th right>{t('admin.colSuccessRate')}</Th>
                  <Th right>{t('admin.colRecords')}</Th>
                  <Th>{t('admin.colDailyQuota')}</Th>
                  <Th right>{t('admin.colMinuteLimit')}</Th>
                  <Th>{t('admin.colAvailable')}</Th>
                  <Th>{t('admin.colLastRun')}</Th>
                </tr>
              </thead>
              <tbody>
                {providers.map(p => (
                  <tr key={p.provider} className="hover:bg-[var(--fd-bg-elev)] transition-colors">
                    <Td mono>{p.provider}</Td>
                    <Td right>{p.attempted > 0 ? fmtNum(p.attempted, locale) : <span className="text-[#444]">—</span>}</Td>
                    <Td right>{p.succeeded > 0 ? fmtNum(p.succeeded, locale) : <span className="text-[#444]">—</span>}</Td>
                    <Td right>
                      {p.success_rate != null ? (
                        <span className={clsx('font-semibold', p.success_rate >= 90 ? 'text-[var(--color-stock-up)]' : p.success_rate >= 60 ? 'text-[#f59e0b]' : 'text-[var(--color-stock-down)]')}>
                          {p.success_rate.toFixed(1)}%
                        </span>
                      ) : <span className="text-[#444]">—</span>}
                    </Td>
                    <Td right>{p.records > 0 ? fmtNum(p.records, locale) : <span className="text-[#444]">—</span>}</Td>
                    <td className="px-3 py-2 border-b border-[#0d1520] min-w-[140px]">
                      <QuotaBar used={p.daily_used} limit={p.daily_limit} />
                    </td>
                    <Td right muted={!p.minute_limit}>{p.minute_limit ?? '—'}</Td>
                    <Td>
                      <span className={clsx('text-[10px] font-semibold px-1.5 py-0.5', p.is_available ? 'bg-[#0a1f15] text-[var(--color-stock-up)]' : 'bg-[#1a0808] text-[var(--color-stock-down)]')}>
                        {p.is_available ? t('admin.available') : t('admin.unavailable')}
                      </span>
                    </Td>
                    <Td muted>{fmtRelative(p.last_run)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Exchange coverage + freshness ── */}
      <section>
        <SectionHeading label={t('admin.sectionExchanges')} />
        <div className="overflow-x-auto border border-[var(--fd-rule)]">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr>
                <Th>{t('admin.colExchange')}</Th>
                <Th right>{t('admin.colTotal')}</Th>
                <Th right>{t('admin.colQuotedToday')}</Th>
                <Th>{t('admin.colCoverage')}</Th>
                <Th>{t('admin.colLatestHistory')}</Th>
                <Th right>{t('admin.colDataLag')}</Th>
              </tr>
            </thead>
            <tbody>
              {exchanges.map(ex => {
                const lagOk = ex.data_lag_days != null && ex.data_lag_days <= 3
                const lagWarn = ex.data_lag_days != null && ex.data_lag_days <= 10
                return (
                  <tr key={ex.exchange} className="hover:bg-[var(--fd-bg-elev)] transition-colors">
                    <Td mono>{ex.exchange}</Td>
                    <Td right>{fmtNum(ex.total, locale)}</Td>
                    <Td right>{ex.quoted_today > 0 ? fmtNum(ex.quoted_today, locale) : <span className="text-[#444]">—</span>}</Td>
                    <td className="px-3 py-2 border-b border-[#0d1520] min-w-[160px]">
                      <CoverageBar pct={ex.coverage_pct} />
                    </td>
                    <Td muted={!ex.latest_historical_date}>{ex.latest_historical_date ?? '—'}</Td>
                    <Td right>
                      {ex.data_lag_days != null ? (
                        <span className={clsx('font-semibold', lagOk ? 'text-[var(--color-stock-up)]' : lagWarn ? 'text-[#f59e0b]' : 'text-[var(--color-stock-down)]')}>
                          {ex.data_lag_days}{t('admin.days')}
                        </span>
                      ) : <span className="text-[#444]">—</span>}
                    </Td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Scheduled jobs ── */}
      <section>
        <SectionHeading label={t('admin.sectionJobs')} />
        <div className="overflow-x-auto border border-[var(--fd-rule)]">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr>
                <Th>{t('admin.colJob')}</Th>
                <Th>{t('admin.colStatus')}</Th>
                <Th right>{t('admin.colRuns')}</Th>
                <Th right>{t('admin.colAttempted')}</Th>
                <Th right>{t('admin.colSucceeded')}</Th>
                <Th right>{t('admin.colRecords')}</Th>
                <Th>{t('admin.colLastRun')}</Th>
              </tr>
            </thead>
            <tbody>
              {jobs.map(j => (
                <tr key={j.job} className="hover:bg-[var(--fd-bg-elev)] transition-colors">
                  <Td mono>{j.job}</Td>
                  <td className="px-3 py-2 border-b border-[#0d1520]"><StatusDot status={j.status} /></td>
                  <Td right>{j.runs}</Td>
                  <Td right muted={j.attempted === 0}>{j.attempted > 0 ? fmtNum(j.attempted, locale) : '—'}</Td>
                  <Td right>
                    <span className={j.status === 'failed' ? 'text-[var(--color-stock-down)]' : 'text-[var(--color-stock-up)]'}>
                      {j.succeeded > 0 ? fmtNum(j.succeeded, locale) : j.attempted > 0 ? '0' : '—'}
                    </span>
                  </Td>
                  <Td right muted={j.records === 0}>{j.records > 0 ? fmtNum(j.records, locale) : '—'}</Td>
                  <Td muted>{fmtRelative(j.last_run)}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Coverage gaps ── */}
      <section>
        <SectionHeading label={t('admin.sectionGaps')} />
        {gaps.total_missing === 0 ? (
          <div className="flex items-center gap-2 px-4 py-3 bg-[#0a1f15] border border-[#10b981]/20 text-[var(--color-stock-up)] text-xs">
            <span className="w-2 h-2 rounded-full bg-[var(--color-stock-up)]" />{t('admin.noGaps')}
          </div>
        ) : (
          <div className="border border-[var(--fd-rule)]">
            <div className="grid grid-cols-[1fr_100px_1fr] px-4 py-2 bg-[#070f1a] border-b border-[var(--fd-rule)]">
              <span className="text-[10px] font-semibold tracking-widest uppercase text-[#a8b4c4]">{t('admin.colExchange')}</span>
              <span className="text-[10px] font-semibold tracking-widest uppercase text-[#a8b4c4] text-right">Missing</span>
              <span />
            </div>
            {Object.entries(gaps.by_exchange)
              .sort((a, b) => b[1] - a[1])
              .map(([ex, count], i, arr) => {
                const exRow = exchanges.find(e => e.exchange === ex)
                const gapPct = exRow ? (count / exRow.total) * 100 : 0
                return (
                  <div key={ex} className={clsx(
                    'grid grid-cols-[1fr_100px_1fr] px-4 py-2.5 items-center hover:bg-[var(--fd-bg-elev)] transition-colors',
                    i < arr.length - 1 && 'border-b border-[#0d1520]'
                  )}>
                    <span className="text-xs font-mono text-[var(--fd-text-secondary)]">{ex}</span>
                    <span className={clsx('text-xs text-right tabular-nums font-semibold', gapPct > 50 ? 'text-[var(--color-stock-down)]' : gapPct > 20 ? 'text-[#f59e0b]' : 'text-[var(--fd-text-secondary)]')}>
                      {fmtNum(count, locale)}
                    </span>
                    <div className="pl-4">
                      <div className="h-1 bg-[var(--fd-rule)] rounded-sm overflow-hidden">
                        <div className={clsx('h-full rounded-sm', gapPct > 50 ? 'bg-[var(--color-stock-down)]' : gapPct > 20 ? 'bg-[#f59e0b]' : 'bg-[#5a8aaa]')} style={{ width: `${Math.min(gapPct, 100)}%` }} />
                      </div>
                    </div>
                  </div>
                )
              })}
            <div className="grid grid-cols-[1fr_100px_1fr] px-4 py-2 bg-[#070f1a] border-t border-[var(--fd-rule)]">
              <span className="text-xs font-semibold text-[#a8b4c4] uppercase tracking-wider">{t('status.total')}</span>
              <span className="text-xs font-semibold text-[var(--fd-text-primary)] text-right tabular-nums">{fmtNum(gaps.total_missing, locale)}</span>
              <span />
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
