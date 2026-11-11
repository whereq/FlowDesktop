import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, type UpcomingEvents } from '../api/client'

function fmtDate(iso: string, lang: string): string {
  try {
    return new Date(iso + 'T00:00:00').toLocaleDateString(lang === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric' })
  } catch { return iso }
}
function daysUntil(iso: string): number {
  const d = new Date(iso + 'T00:00:00')
  const now = new Date(); now.setHours(0, 0, 0, 0)
  return Math.round((d.getTime() - now.getTime()) / 86400000)
}

/** Next-earnings / ex-dividend chips for a stock (StockDetail header). */
export default function EventChips({ symbol }: { symbol: string }) {
  const { t, i18n } = useTranslation()
  const [ev, setEv] = useState<UpcomingEvents | null>(null)

  useEffect(() => {
    let alive = true
    api.getUpcomingEvents(symbol).then(d => { if (alive) setEv(d) }).catch(() => {})
    return () => { alive = false }
  }, [symbol])

  if (!ev || (!ev.next_earnings && !ev.next_dividend)) return null
  const lang = i18n.language

  const Chip = ({ label, value, sub }: { label: string; value: string; sub?: string }) => (
    <span style={{ display: 'inline-flex', flexDirection: 'column', padding: '4px 10px', border: '1px solid var(--color-accent)' }}>
      <span style={{ color: 'var(--color-accent)', fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.1em' }}>{label}</span>
      <span style={{ color: 'var(--fd-text)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
        {value}{sub ? <span style={{ color: 'var(--fd-text-faint)' }}> · {sub}</span> : null}
      </span>
    </span>
  )

  return (
    <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
      {ev.next_earnings && (
        <Chip
          label={t('calendar.nextEarnings', 'NEXT EARNINGS')}
          value={fmtDate(ev.next_earnings.event_date, lang)}
          sub={`${daysUntil(ev.next_earnings.event_date)}d`}
        />
      )}
      {ev.next_dividend && (
        <Chip
          label={t('calendar.exDiv', 'EX-DIV')}
          value={fmtDate(ev.next_dividend.event_date, lang)}
          sub={ev.next_dividend.amount != null ? `${ev.next_dividend.currency === 'USD' ? '$' : ''}${ev.next_dividend.amount}` : undefined}
        />
      )}
    </div>
  )
}
