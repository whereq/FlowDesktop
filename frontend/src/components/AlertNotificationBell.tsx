import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAlerts } from '../hooks/useStocks'

export default function AlertNotificationBell() {
  const { t } = useTranslation()
  const { data: alerts = [], deleteAlert, rearmAlert } = useAlerts()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const triggered = alerts.filter((a) => !a.is_active && a.triggered_at !== null)
  const count = triggered.length

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (alerts.length === 0 && count === 0) return null

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title={t('alerts.notificationTitle')}
        className={`relative flex items-center justify-center w-8 h-8 border transition-colors ${
          open
            ? 'border-[var(--color-accent)] bg-[var(--fd-bg-elev)] text-[var(--color-accent)]'
            : count > 0
              ? 'border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20'
              : 'border-[var(--fd-rule-strong)] bg-[var(--fd-bg-panel)] text-[#8ab4d8] hover:text-[#a8d0f0] hover:bg-[var(--fd-bg-elev)]'
        }`}
      >
        {/* Price-target / crosshair icon — distinct from notification bell */}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="square">
          <circle cx="12" cy="12" r="10"/>
          <circle cx="12" cy="12" r="4"/>
          <line x1="12" y1="2" x2="12" y2="6"/>
          <line x1="12" y1="18" x2="12" y2="22"/>
          <line x1="2" y1="12" x2="6" y2="12"/>
          <line x1="18" y1="12" x2="22" y2="12"/>
        </svg>
        {/* Badge */}
        {count > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[14px] h-[14px] bg-amber-400 text-[#0d0d0d] text-[9px] font-bold rounded-full flex items-center justify-center px-0.5 leading-none">
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 bg-[var(--fd-bg-panel)] border border-[var(--fd-rule-strong)] shadow-2xl z-50">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--fd-rule)]">
            <p className="text-[11px] font-semibold text-[#c8d8ea] tracking-widest uppercase">
              {t('alerts.triggered')} ({count})
            </p>
            <Link
              to="/watchlist"
              onClick={() => setOpen(false)}
              className="text-[10px] text-[#4a7090] hover:text-[#7ab0d8] transition-colors"
            >
              {t('alerts.viewAll')} →
            </Link>
          </div>

          {count === 0 ? (
            <p className="text-[#666] text-xs px-4 py-4 text-center">{t('alerts.noTriggered')}</p>
          ) : (
            <div className="max-h-72 overflow-auto">
              {triggered.map((a) => {
                const isPct = a.alert_type.includes('change_pct')
                const val = isPct
                  ? `${a.threshold > 0 ? '+' : ''}${a.threshold}%`
                  : a.threshold.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                return (
                  <div key={a.id} className="flex items-center gap-3 px-4 py-2.5 border-b border-[#111] last:border-0 hover:bg-[var(--fd-bg-elev)]">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[var(--fd-text-primary)] text-xs font-semibold">{a.symbol}</p>
                      <p className="text-[var(--fd-text-dim)] text-[10px]">
                        {t(`alerts.type_${a.alert_type}`)} <span className="text-[var(--fd-text-dim)]">{val}</span>
                      </p>
                      {a.triggered_at && (
                        <p className="text-[var(--fd-text-faint)] text-[9px] mt-0.5">
                          {new Date(a.triggered_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-1 flex-shrink-0">
                      <button
                        onClick={() => rearmAlert(a.id)}
                        title={t('alerts.rearm')}
                        className="text-[9px] px-1.5 py-0.5 border border-[var(--fd-rule-strong)] text-[#7ab0d8] hover:border-[var(--color-accent)] transition-colors"
                      >
                        {t('alerts.rearm')}
                      </button>
                      <button
                        onClick={() => deleteAlert(a.id)}
                        title={t('alerts.delete')}
                        className="text-[var(--fd-text-faint)] hover:text-red-400 transition-colors p-0.5"
                      >
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M18 6L6 18M6 6l12 12"/>
                        </svg>
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Footer */}
          <div className="border-t border-[var(--fd-rule)] px-4 py-2 flex items-center justify-between">
            <p className="text-[var(--fd-text-faint)] text-[10px]">{alerts.length} {t('alerts.totalAlerts')}</p>
            <Link
              to="/watchlist"
              onClick={() => setOpen(false)}
              className="text-[10px] text-[var(--color-accent)] hover:text-[var(--color-nova)] transition-colors font-medium"
            >
              {t('alerts.manageAlerts')}
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
