import { useTranslation } from 'react-i18next'
import { useSystemStatus } from '../hooks/useStocks'
import { useAuth } from '../auth/useAuth'
import clsx from 'clsx'

/* ─── Helpers ───────────────────────────────────────────────────────────────── */

function fmtNum(v: number | null | undefined, locale: string) {
  return v == null ? '—' : v.toLocaleString(locale)
}

function fmtPct(v: number) {
  return `${v.toFixed(1)}%`
}

function fmtTime(v: string | null | undefined, locale: string) {
  if (!v) return '—'
  return new Date(v).toLocaleString(locale, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function fmtRelative(iso: string): string {
  // Normalize: if no timezone suffix, treat as UTC
  const hasTz = iso.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(iso)
  const normalized = hasTz ? iso : iso + 'Z'
  const diff = Math.floor((Date.now() - new Date(normalized).getTime()) / 1000)
  if (diff <= 0) return 'just now'
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) {
    const m = Math.floor(diff / 60), s = diff % 60
    return `${m}m ${s}s ago`
  }
  if (diff < 86400) {
    const h = Math.floor(diff / 3600), m = Math.floor((diff % 3600) / 60)
    return `${h}h ${m}m ago`
  }
  const d = Math.floor(diff / 86400), h = Math.floor((diff % 86400) / 3600)
  return `${d}d ${h}h ago`
}

/* ─── Sub-components ────────────────────────────────────────────────────────── */

function SectionHeading({ label }: { label: string }) {
  return (
    <h2 className="text-sm font-bold tracking-widest uppercase text-[var(--fd-text-secondary)] border-l-2 border-[var(--color-accent)] pl-3 leading-none mb-3">
      {label}
    </h2>
  )
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-surface-card border border-border p-4 flex flex-col gap-1">
      <p className="text-[10px] font-semibold tracking-widest uppercase text-[var(--fd-text-dim)]">{label}</p>
      <p className="text-xl font-semibold text-[var(--fd-text-primary)] leading-tight">{value}</p>
      {sub && <p className="text-[10px] text-[var(--fd-text-dim)]">{sub}</p>}
    </div>
  )
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === 'completed' || status === 'ok' ? 'bg-[var(--color-stock-up)]'
    : status === 'failed' ? 'bg-[var(--color-stock-down)]'
    : status === 'running' ? 'bg-[#f59e0b] animate-pulse'
    : 'bg-[var(--fd-text-faint)]'
  return <span className={clsx('inline-block w-2 h-2 rounded-full shrink-0', color)} />
}

function CoverageBar({ pct }: { pct: number }) {
  const color =
    pct >= 80 ? 'bg-[var(--color-stock-up)]'
    : pct >= 50 ? 'bg-[#f59e0b]'
    : pct > 0   ? 'bg-[var(--color-stock-down)]'
    : 'bg-[var(--fd-rule)]'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-[var(--fd-rule)] rounded-sm overflow-hidden">
        <div className={clsx('h-full rounded-sm transition-all', color)} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="text-xs text-[var(--fd-text-dim)] w-10 text-right tabular-nums">{fmtPct(pct)}</span>
    </div>
  )
}

/* ─── Page ──────────────────────────────────────────────────────────────────── */

export default function SystemStatus() {
  const { t, i18n } = useTranslation()
  const locale = i18n.language === 'zh' ? 'zh-CN' : 'en-US'
  const { roles } = useAuth()
  const isAdmin = roles.includes('fd-admin')

  const { data, isLoading, error, dataUpdatedAt } = useSystemStatus()

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-32 bg-surface-card border border-border" />
        ))}
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="border border-[#ef4444]/40 bg-[#1a0808] p-6 text-[var(--color-stock-down)] text-sm">
        {t('status.loadError')}
      </div>
    )
  }

  const { db, coverage, jobs_today, last_updated } = data

  /* ── Derived totals ── */
  const totalActive  = coverage.reduce((s, r) => s + r.total, 0)
  const totalQuoted  = coverage.reduce((s, r) => s + r.quoted_today, 0)
  const overallPct   = totalActive > 0 ? (totalQuoted / totalActive) * 100 : 0
  const jobsOk       = jobs_today.filter(j => j.status === 'completed' || j.status === 'ok').length
  const jobsFail     = jobs_today.filter(j => j.status === 'failed').length

  return (
    <div className="space-y-8">

      {/* ── Page header ── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-lg font-bold text-[var(--fd-text-primary)] tracking-tight">{t('status.title')}</h1>
          <p className="text-xs text-[var(--fd-text-dim)] mt-0.5">
            {t('status.updatedAt', { time: fmtRelative(last_updated) })}
            {dataUpdatedAt ? ` · ${t('status.fetched')} ${fmtRelative(new Date(dataUpdatedAt).toISOString())}` : ''}
          </p>
        </div>
        {/* Health pill */}
        <div className={clsx(
          'flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border',
          jobsFail === 0 && overallPct >= 70
            ? 'border-[#10b981]/40 bg-[#0a1f15] text-[var(--color-stock-up)]'
            : jobsFail > 0 || overallPct < 30
            ? 'border-[#ef4444]/40 bg-[#1a0808] text-[var(--color-stock-down)]'
            : 'border-[#f59e0b]/40 bg-[#1a1000] text-[#f59e0b]'
        )}>
          <span className={clsx(
            'w-1.5 h-1.5 rounded-full',
            jobsFail === 0 && overallPct >= 70 ? 'bg-[var(--color-stock-up)]'
            : jobsFail > 0 || overallPct < 30 ? 'bg-[var(--color-stock-down)]'
            : 'bg-[#f59e0b]'
          )} />
          {jobsFail === 0 && overallPct >= 70 ? t('status.healthOk')
            : jobsFail > 0 ? t('status.healthDegraded')
            : t('status.healthPartial')}
        </div>
      </div>

      {/* ── Database snapshot ── */}
      <section>
        <SectionHeading label={t('status.sectionDatabase')} />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-[var(--fd-rule)] border border-border">
          <StatCard label={t('stats.totalStocks')}      value={fmtNum(db.stocks, locale)} />
          <StatCard label={t('stats.totalQuotes')}      value={fmtNum(db.quotes, locale)} />
          <StatCard label={t('stats.historicalRecords')} value={fmtNum(db.historical_records, locale)} />
          <StatCard label={t('stats.lastUpdate')}       value={fmtTime(db.last_quote, locale)} />
        </div>
      </section>

      {/* ── Quote coverage by exchange ── */}
      <section>
        <SectionHeading label={t('status.sectionCoverage')} />
        <div className="border border-border bg-surface-card overflow-hidden">
          {/* Header */}
          <div className="grid grid-cols-[1fr_80px_80px_140px] gap-4 px-4 py-2 border-b border-[var(--fd-rule)] bg-[var(--fd-bg)]">
            <span className="text-[10px] font-semibold tracking-widest uppercase text-[var(--fd-text-dim)]">{t('status.colExchange')}</span>
            <span className="text-[10px] font-semibold tracking-widest uppercase text-[var(--fd-text-dim)] text-right">{t('status.colTotal')}</span>
            <span className="text-[10px] font-semibold tracking-widest uppercase text-[var(--fd-text-dim)] text-right">{t('status.colToday')}</span>
            <span className="text-[10px] font-semibold tracking-widest uppercase text-[var(--fd-text-dim)]">{t('status.colCoverage')}</span>
          </div>
          {coverage.map((row, i) => (
            <div
              key={row.exchange}
              className={clsx(
                'grid grid-cols-[1fr_80px_80px_140px] gap-4 px-4 py-2.5 items-center',
                i < coverage.length - 1 && 'border-b border-[#111]',
                'hover:bg-surface-raised transition-colors'
              )}
            >
              <span className="text-sm font-medium text-[var(--fd-text-primary)]">
                {t(`exchanges.${row.exchange}`, row.exchange)}
              </span>
              <span className="text-sm text-[var(--fd-text-dim)] text-right tabular-nums">
                {fmtNum(row.total, locale)}
              </span>
              <span className="text-sm text-[var(--fd-text-dim)] text-right tabular-nums">
                {row.quoted_today > 0 ? fmtNum(row.quoted_today, locale) : '—'}
              </span>
              <CoverageBar pct={row.pct} />
            </div>
          ))}
          {/* Summary row */}
          <div className="grid grid-cols-[1fr_80px_80px_140px] gap-4 px-4 py-2.5 items-center border-t border-[var(--fd-rule)] bg-[var(--fd-bg)]">
            <span className="text-xs font-semibold text-[var(--fd-text-dim)] uppercase tracking-wider">{t('status.total')}</span>
            <span className="text-sm font-semibold text-[var(--fd-text-primary)] text-right tabular-nums">{fmtNum(totalActive, locale)}</span>
            <span className="text-sm font-semibold text-[var(--fd-text-primary)] text-right tabular-nums">{fmtNum(totalQuoted, locale)}</span>
            <CoverageBar pct={overallPct} />
          </div>
        </div>
      </section>

      {/* ── Collection jobs today ── */}
      <section>
        <SectionHeading label={t('status.sectionJobs')} />
        {jobs_today.length === 0 ? (
          <p className="text-sm text-[var(--fd-text-dim)] py-4">{t('status.noJobsToday')}</p>
        ) : (
          <div className="border border-border bg-surface-card overflow-hidden">
            <div className="grid grid-cols-[2fr_60px_60px_80px_80px] gap-4 px-4 py-2 border-b border-[var(--fd-rule)] bg-[var(--fd-bg)]">
              <span className="text-[10px] font-semibold tracking-widest uppercase text-[var(--fd-text-dim)]">{t('status.colJob')}</span>
              <span className="text-[10px] font-semibold tracking-widest uppercase text-[var(--fd-text-dim)] text-center">{t('status.colStatus')}</span>
              <span className="text-[10px] font-semibold tracking-widest uppercase text-[var(--fd-text-dim)] text-right">{t('status.colRuns')}</span>
              <span className="text-[10px] font-semibold tracking-widest uppercase text-[var(--fd-text-dim)] text-right">{t('status.colAttempted')}</span>
              <span className="text-[10px] font-semibold tracking-widest uppercase text-[var(--fd-text-dim)] text-right">{t('status.colSucceeded')}</span>
            </div>
            {jobs_today.map((job, i) => (
              <div
                key={job.job}
                className={clsx(
                  'grid grid-cols-[2fr_60px_60px_80px_80px] gap-4 px-4 py-2.5 items-center',
                  i < jobs_today.length - 1 && 'border-b border-[#111]',
                  'hover:bg-surface-raised transition-colors'
                )}
              >
                <span className="text-sm text-[var(--fd-text-secondary)] font-mono text-xs truncate">{job.job}</span>
                <span className="flex justify-center">
                  <StatusDot status={job.status} />
                </span>
                <span className="text-sm text-[var(--fd-text-dim)] text-right tabular-nums">{job.runs}</span>
                <span className="text-sm text-[var(--fd-text-dim)] text-right tabular-nums">
                  {job.attempted > 0 ? fmtNum(job.attempted, locale) : '—'}
                </span>
                <span className={clsx(
                  'text-sm text-right tabular-nums',
                  job.status === 'failed' ? 'text-[var(--color-stock-down)]' : 'text-[var(--color-stock-up)]'
                )}>
                  {job.succeeded > 0 ? fmtNum(job.succeeded, locale) : job.attempted > 0 ? '0' : '—'}
                </span>
              </div>
            ))}
            {/* Jobs summary */}
            <div className="flex items-center gap-4 px-4 py-2 border-t border-[var(--fd-rule)] bg-[var(--fd-bg)] text-xs text-[var(--fd-text-dim)]">
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-stock-up)]" />
                {t('status.jobsOk', { n: jobsOk })}
              </span>
              {jobsFail > 0 && (
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-stock-down)]" />
                  {t('status.jobsFailed', { n: jobsFail })}
                </span>
              )}
            </div>
          </div>
        )}
      </section>

      {/* ── Admin note ── */}
      {isAdmin && (
        <section>
          <SectionHeading label={t('status.sectionAdmin')} />
          <p className="text-xs text-[var(--fd-text-dim)]">{t('status.adminHint')}</p>
        </section>
      )}
    </div>
  )
}
