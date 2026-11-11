import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, type CalendarEvent } from '../api/client'
import { useWatchlistContext } from '../contexts/useWatchlistContext'

function fmtDay(iso: string, lang: string): string {
  try {
    return new Date(iso + 'T00:00:00').toLocaleDateString(lang === 'zh' ? 'zh-CN' : 'en-US', {
      weekday: 'short', month: 'short', day: 'numeric',
    })
  } catch { return iso }
}

const RANGE_DAYS = 30

export default function Calendar() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const { symbols: watchSymbols } = useWatchlistContext()
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [kind, setKind] = useState<'all' | 'earnings' | 'dividend'>('all')
  const [watchOnly, setWatchOnly] = useState(false)

  useEffect(() => {
    let alive = true
    setLoading(true)
    const today = new Date()
    const to = new Date(today.getTime() + RANGE_DAYS * 86400000)
    const iso = (d: Date) => d.toISOString().slice(0, 10)
    const params: { from: string; to: string; kind?: string; symbols?: string; limit: number } = {
      from: iso(today), to: iso(to), limit: 500,
    }
    if (kind !== 'all') params.kind = kind
    if (watchOnly) params.symbols = watchSymbols.join(',')
    if (watchOnly && watchSymbols.length === 0) {
      setEvents([]); setLoading(false); return
    }
    api.getCalendarEvents(params)
      .then(r => { if (alive) setEvents(r.events) })
      .catch(() => { if (alive) setEvents([]) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [kind, watchOnly, watchSymbols.join(',')]) // eslint-disable-line react-hooks/exhaustive-deps

  // Group by date (ordered; API already returns ascending by date).
  const grouped = useMemo(() => {
    const m = new Map<string, CalendarEvent[]>()
    for (const ev of events) {
      if (!m.has(ev.event_date)) m.set(ev.event_date, [])
      m.get(ev.event_date)!.push(ev)
    }
    return [...m.entries()]
  }, [events])

  const Tab = ({ v, label }: { v: typeof kind; label: string }) => (
    <button onClick={() => setKind(v)}
      style={{
        fontSize: 12, padding: '5px 12px', borderRadius: 2, cursor: 'pointer',
        border: '1px solid var(--fd-rule)',
        background: kind === v ? 'var(--fd-bg-elev)' : 'transparent',
        color: kind === v ? 'var(--color-nova)' : 'var(--fd-text-dim)',
      }}>{label}</button>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, fontFamily: 'var(--font-ui)' }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--fd-text)' }}>{t('calendar.title', 'Calendar')}</h1>
        <p style={{ fontSize: 13, color: 'var(--fd-text-dim)', marginTop: 2 }}>
          {t('calendar.subtitle', 'Upcoming earnings and dividends over the next 30 days.')}
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <Tab v="all" label={t('calendar.all', 'All')} />
        <Tab v="earnings" label={t('calendar.earnings', 'Earnings')} />
        <Tab v="dividend" label={t('calendar.dividend', 'Dividend')} />
        <span style={{ flex: 1 }} />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fd-text-dim)', cursor: 'pointer' }}>
          <input type="checkbox" checked={watchOnly} onChange={() => setWatchOnly(v => !v)} />
          {t('calendar.watchlistOnly', 'My watchlist only')}
        </label>
      </div>

      {loading && <p style={{ color: 'var(--fd-text-dim)', fontSize: 13 }}>{t('common.loading', 'Loading…')}</p>}
      {!loading && grouped.length === 0 && (
        <p style={{ color: 'var(--fd-text-faint)', fontSize: 13 }}>
          {watchOnly ? t('calendar.none', 'No upcoming events in your watchlist') : t('calendar.noneAll', 'No upcoming events in this window.')}
        </p>
      )}

      {!loading && grouped.map(([day, evs]) => (
        <section key={day} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <h2 style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--fd-text-faint)', borderLeft: '2px solid var(--color-accent)', paddingLeft: 8 }}>
            {fmtDay(day, lang)}
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {evs.map((ev, i) => (
              <Link key={`${ev.symbol}-${ev.kind}-${i}`} to={`/stock/${ev.symbol}`}
                style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', borderBottom: '1px solid var(--fd-rule)', textDecoration: 'none' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--color-nova)', minWidth: 72 }}>{ev.symbol}</span>
                <span style={{
                  fontSize: 9, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', padding: '2px 6px',
                  borderRadius: 2, border: '1px solid var(--fd-rule)',
                  color: ev.kind === 'earnings' ? 'var(--color-nova)' : 'var(--color-accent)',
                }}>
                  {ev.kind === 'earnings' ? t('calendar.earnings', 'Earnings') : t('calendar.dividend', 'Dividend')}
                </span>
                <span style={{ fontSize: 12, color: 'var(--fd-text-dim)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {ev.name || ''}
                </span>
                {ev.kind === 'earnings' && ev.eps_estimate != null && (
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fd-text-faint)' }}>
                    {t('calendar.estimate', 'est.')} {ev.eps_estimate}
                  </span>
                )}
                {ev.kind === 'dividend' && ev.amount != null && (
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fd-text)' }}>
                    {ev.currency === 'USD' ? '$' : ''}{ev.amount}
                  </span>
                )}
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
