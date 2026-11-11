import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { pushSupported, isPushSubscribed, enablePush } from '../utils/push'
import { api } from '../api/client'
import { lsGet, lsSet } from '../utils/storage'

const DISMISS_KEY = 'pulse_banner_dismissed'

/**
 * Discoverable, dismissible CTA that drives Web Push adoption for NOVA Pulse.
 * Push-subscribe otherwise lives only in Settings (hence 0 subscribers). Shown to
 * authenticated users whose browser supports push, where the server has push
 * enabled, who aren't already subscribed, and who haven't dismissed it.
 */
export default function PulseEnableBanner() {
  const { t } = useTranslation()
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    let alive = true
    ;(async () => {
      if (lsGet(DISMISS_KEY) === '1' || !pushSupported()) return
      try {
        const status = await api.getPushStatus()
        if (!status.enabled || status.subscribed) return
      } catch { return }
      const subbed = await isPushSubscribed().catch(() => false)
      if (alive && !subbed) setShow(true)
    })()
    return () => { alive = false }
  }, [])

  if (!show) return null

  const enable = async () => {
    setErr('')
    setBusy(true)
    try {
      await enablePush()
      setShow(false)
    } catch (e) {
      const msg = (e as Error).message
      setErr(
        msg === 'denied'
          ? t('pulse.bannerDenied', 'Blocked in your browser — allow notifications for this site, then retry.')
          : t('pulse.bannerError', 'Could not enable. You can also turn it on from Settings.')
      )
    } finally {
      setBusy(false)
    }
  }

  const dismiss = () => {
    lsSet(DISMISS_KEY, '1')
    setShow(false)
  }

  return (
    <div className="flex items-center gap-3 px-3 py-2 border border-[var(--color-nova)]/30 bg-[var(--color-nova)]/5 text-[12px]">
      <span className="text-base leading-none" aria-hidden>✨</span>
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-[var(--fd-text)]">
          {t('pulse.bannerTitle', 'Turn on NOVA Pulse')}
        </div>
        <div className="text-[var(--fd-text-dim)] leading-snug">
          {t('pulse.bannerBody', 'Get proactive, personalized alerts the moment something moves on your watchlist — analysis, not advice.')}
        </div>
        {err && <div className="text-amber-500 text-[11px] mt-0.5">{err}</div>}
      </div>
      <button
        onClick={enable}
        disabled={busy}
        className="shrink-0 text-[11px] font-semibold px-2 py-1 border border-[var(--color-nova)]/50 text-[var(--color-nova)] hover:bg-[var(--color-nova)]/10 disabled:opacity-50 transition-colors"
      >
        {busy ? t('pulse.bannerEnabling', 'Enabling…') : t('pulse.bannerEnable', 'Enable')}
      </button>
      <button
        onClick={dismiss}
        title={t('pulse.bannerDismiss', 'Dismiss')}
        className="shrink-0 text-[var(--fd-text-faint)] hover:text-[var(--fd-text)] px-1"
      >
        ✕
      </button>
    </div>
  )
}
