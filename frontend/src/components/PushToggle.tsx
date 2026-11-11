import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { pushSupported, isPushSubscribed, enablePush, disablePush } from '../utils/push'
import { api } from '../api/client'

/** Working toggle for browser (Web Push) notifications, used in Settings. */
export default function PushToggle() {
  const { t } = useTranslation()
  const [on, setOn] = useState(false)
  const [busy, setBusy] = useState(false)
  const [available, setAvailable] = useState(true)
  const [err, setErr] = useState('')

  useEffect(() => {
    let alive = true
    ;(async () => {
      if (!pushSupported()) { if (alive) setAvailable(false); return }
      try {
        const status = await api.getPushStatus()
        if (!status.enabled) { if (alive) setAvailable(false); return }
      } catch { /* treat as available; surface errors on toggle */ }
      const sub = await isPushSubscribed().catch(() => false)
      if (alive) setOn(sub)
    })()
    return () => { alive = false }
  }, [])

  const toggle = async () => {
    setErr('')
    setBusy(true)
    try {
      if (on) { await disablePush(); setOn(false) }
      else { await enablePush(); setOn(true) }
    } catch (e) {
      const msg = (e as Error).message
      setErr(
        msg === 'denied' ? t('settings.pushDenied', 'Blocked in browser settings')
        : msg === 'unsupported' ? t('settings.pushUnsupported', 'Not supported here')
        : msg === 'server-disabled' ? t('settings.pushUnavailable', 'Unavailable')
        : t('settings.pushError', 'Could not update')
      )
    } finally {
      setBusy(false)
    }
  }

  if (!available) {
    return <span className="text-xs text-[var(--fd-text-faint)]">{t('settings.pushUnsupported', 'Not supported here')}</span>
  }

  const sendTest = async () => {
    setErr('')
    try { await api.testPush() } catch { setErr(t('settings.pushError', 'Could not update')) }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <label className="relative inline-flex items-center cursor-pointer">
        <input type="checkbox" className="sr-only peer" checked={on} disabled={busy} onChange={toggle} />
        <div className="w-9 h-5 bg-[var(--fd-rule)] peer-focus:ring-1 peer-focus:ring-[var(--color-accent)] rounded-full peer peer-checked:bg-[var(--color-accent)] transition-colors after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-[var(--fd-text-dim)] after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full peer-checked:after:bg-white" />
      </label>
      {on && !busy && (
        <button onClick={sendTest} className="text-[10px] text-[var(--color-accent)] hover:underline">
          {t('settings.pushSendTest', 'Send test')}
        </button>
      )}
      {err && <span className="text-[10px] text-amber-500">{err}</span>}
    </div>
  )
}
