import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, type NotificationPrefs } from '../api/client'

const LOCAL_TZ = (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' } catch { return 'UTC' } })()

const SWITCH =
  "w-9 h-5 bg-[var(--fd-rule)] peer-focus:ring-1 peer-focus:ring-[var(--color-accent)] rounded-full peer peer-checked:bg-[var(--color-accent)] transition-colors after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-[var(--fd-text-dim)] after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full peer-checked:after:bg-white"

function Toggle({ on, onChange, disabled }: { on: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <label className="relative inline-flex items-center cursor-pointer">
      <input type="checkbox" className="sr-only peer" checked={on} disabled={disabled} onChange={onChange} />
      <div className={SWITCH} />
    </label>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="text-sm text-[var(--fd-text)]">{label}</span>
      {children}
    </div>
  )
}

/** Per-category push toggles + quiet hours, auto-saved. */
export default function NotificationPrefsPanel() {
  const { t } = useTranslation()
  const [p, setP] = useState<NotificationPrefs | null>(null)

  useEffect(() => {
    let alive = true
    api.getNotificationPrefs().then(d => { if (alive) setP(d) }).catch(() => {})
    return () => { alive = false }
  }, [])

  const save = (next: NotificationPrefs) => {
    setP(next)
    api.updateNotificationPrefs({ ...next, tz: LOCAL_TZ }).catch(() => {})
  }
  const set = <K extends keyof NotificationPrefs>(k: K, v: NotificationPrefs[K]) => {
    if (!p) return
    save({ ...p, [k]: v })
  }

  if (!p) return null

  const HOURS = Array.from({ length: 24 }, (_, i) => i)
  const hh = (n: number) => String(n).padStart(2, '0') + ':00'

  return (
    <div className="flex flex-col gap-0.5 pt-1">
      <div className="text-[10px] uppercase tracking-wider text-[var(--fd-text-faint)] font-semibold pb-1">
        {t('settings.pushCategories', 'Push these to the browser')}
      </div>
      <Row label={t('settings.catAlerts', 'Price alerts')}>
        <Toggle on={p.push_alerts} onChange={() => set('push_alerts', !p.push_alerts)} />
      </Row>
      <Row label={t('settings.catVolume', 'Volume spikes')}>
        <Toggle on={p.push_volume} onChange={() => set('push_volume', !p.push_volume)} />
      </Row>
      <Row label={t('settings.catSignals', 'Market signals & news')}>
        <Toggle on={p.push_signals} onChange={() => set('push_signals', !p.push_signals)} />
      </Row>
      <Row label={t('settings.catAgent', 'Scheduled agent briefs')}>
        <Toggle on={p.push_agent} onChange={() => set('push_agent', !p.push_agent)} />
      </Row>
      <Row label={t('settings.catEvents', 'Earnings & dividend reminders')}>
        <Toggle on={p.push_events} onChange={() => set('push_events', !p.push_events)} />
      </Row>

      <div className="border-t border-[var(--fd-rule)] my-2" />

      <Row label={t('settings.proactiveDigest', 'NOVA Pulse: one daily digest')}>
        <Toggle on={p.proactive_digest} onChange={() => set('proactive_digest', !p.proactive_digest)} />
      </Row>
      <p className="text-[10px] text-[var(--fd-text-faint)] pl-1 pb-1 leading-snug">
        {t('settings.proactiveDigestHint', 'Bundle proactive watchlist insights into one daily summary instead of individual pushes.')}
      </p>

      <div className="border-t border-[var(--fd-rule)] my-2" />

      <Row label={t('settings.quietHours', 'Quiet hours')}>
        <Toggle on={p.quiet_enabled} onChange={() => set('quiet_enabled', !p.quiet_enabled)} />
      </Row>
      {p.quiet_enabled && (
        <div className="flex items-center gap-2 pl-1 pb-1">
          <span className="text-xs text-[var(--fd-text-dim)]">{t('settings.quietFrom', 'From')}</span>
          <select value={p.quiet_start} onChange={e => set('quiet_start', parseInt(e.target.value, 10))}
            className="text-xs bg-[var(--fd-bg)] border border-[var(--fd-rule)] rounded-sm px-1.5 py-1 text-[var(--fd-text)]">
            {HOURS.map(h => <option key={h} value={h}>{hh(h)}</option>)}
          </select>
          <span className="text-xs text-[var(--fd-text-dim)]">{t('settings.quietTo', 'to')}</span>
          <select value={p.quiet_end} onChange={e => set('quiet_end', parseInt(e.target.value, 10))}
            className="text-xs bg-[var(--fd-bg)] border border-[var(--fd-rule)] rounded-sm px-1.5 py-1 text-[var(--fd-text)]">
            {HOURS.map(h => <option key={h} value={h}>{hh(h)}</option>)}
          </select>
          <span className="text-[10px] text-[var(--fd-text-faint)] font-mono">{LOCAL_TZ}</span>
        </div>
      )}
    </div>
  )
}
