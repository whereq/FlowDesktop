import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, type CalendarEvent } from '../api/client'

function fmtDate(iso: string, lang: string): string {
  try {
    return new Date(iso + 'T00:00:00').toLocaleDateString(lang === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric' })
  } catch { return iso }
}

/** Compact upcoming earnings/dividends for the user's watchlist (Dashboard). */
export default function UpcomingEventsWidget({ symbols }: { symbols: string[] }) {
  const { t, i18n } = useTranslation()
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [loaded, setLoaded] = useState(false)
  const lang = i18n.language

  useEffect(() => {
    if (!symbols.length) { setLoaded(true); return }
    let alive = true
    const today = new Date()
    const to = new Date(today.getTime() + 30 * 86400000)
    const iso = (d: Date) => d.toISOString().slice(0, 10)
    api.getCalendarEvents({ from: iso(today), to: iso(to), symbols: symbols.join(','), limit: 12 })
      .then(r => { if (alive) { setEvents(r.events); setLoaded(true) } })
      .catch(() => { if (alive) setLoaded(true) })
    return () => { alive = false }
  }, [symbols.join(',')]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!loaded || (loaded && events.length === 0)) return null

  return (
    <div style={{ border: '1px solid var(--fd-rule)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--fd-rule)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: 'var(--color-accent)', fontSize: 13 }}>📅</span>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--fd-text-faint)' }}>
          {t('calendar.upcoming', 'Upcoming events')}
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {events.slice(0, 8).map((ev, i) => (
          <Link key={`${ev.symbol}-${ev.kind}-${i}`} to={`/stock/${ev.symbol}`}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px', borderBottom: '1px solid var(--fd-rule)', textDecoration: 'none' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-nova)', minWidth: 64 }}>{ev.symbol}</span>
            <span style={{
              fontSize: 9, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', padding: '1px 5px',
              borderRadius: 2, border: '1px solid var(--fd-rule)',
              color: ev.kind === 'earnings' ? 'var(--color-nova)' : 'var(--color-accent)',
            }}>
              {ev.kind === 'earnings' ? t('calendar.earnings', 'Earnings') : t('calendar.dividend', 'Dividend')}
            </span>
            <span style={{ flex: 1 }} />
            {ev.kind === 'dividend' && ev.amount != null && (
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fd-text-dim)' }}>
                {ev.currency === 'USD' ? '$' : ''}{ev.amount}
              </span>
            )}
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fd-text)' }}>{fmtDate(ev.event_date, lang)}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
