import { useState, useEffect, useRef, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useAlerts } from '../hooks/useStocks'
import { CURRENCIES, currencyForExchange, type Currency } from '../utils/alertCurrency'
import type { AlertType } from '../api/client'

const ALERT_TYPES: AlertType[] = ['price_above', 'price_below', 'change_pct_above', 'change_pct_below']
const isPct = (t: AlertType) => t.includes('change_pct')

interface Props {
  symbol: string
  exchange?: string | null
  currentPrice?: number | null
  onClose: () => void
}

export default function SetAlertModal({ symbol, exchange, currentPrice, onClose }: Props) {
  const { t } = useTranslation()
  const { createAlert } = useAlerts()
  const ref = useRef<HTMLDivElement>(null)

  const [alertType, setAlertType] = useState<AlertType>('price_above')
  const [threshold, setThreshold] = useState(currentPrice?.toFixed(2) ?? '')
  const [currency, setCurrency] = useState<Currency>(currencyForExchange(exchange))
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset threshold when switching between price ↔ pct types
  useEffect(() => {
    if (isPct(alertType)) {
      setThreshold('5')
    } else {
      setThreshold(currentPrice?.toFixed(2) ?? '')
    }
  }, [alertType, currentPrice])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const val = parseFloat(threshold)
    if (isNaN(val)) { setError(t('alerts.invalidInput')); return }
    setSaving(true)
    setError(null)
    try {
      await createAlert(symbol, alertType, val)
      setDone(true)
      setTimeout(onClose, 900)
    } catch {
      setError(t('alerts.saveError'))
    } finally {
      setSaving(false)
    }
  }

  return (
    /* backdrop */
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div ref={ref} className="bg-[var(--fd-bg-panel)] border border-[var(--fd-rule-strong)] shadow-2xl w-80 p-5">

        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-[var(--fd-text-primary)] font-semibold text-sm">{t('alerts.setAlertFor')} <span className="text-[var(--color-nova)]">{symbol}</span></p>
            {currentPrice != null && (
              <p className="text-[var(--fd-text-dim)] text-xs mt-0.5">{t('alerts.currentPrice')}: {currency.symbol}{currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
            )}
          </div>
          <button onClick={onClose} className="text-[var(--fd-text-faint)] hover:text-[var(--fd-text-primary)] transition-colors p-1">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {done ? (
          <div className="flex items-center gap-2 py-4 justify-center">
            <svg className="text-emerald-400 w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
            </svg>
            <p className="text-emerald-400 text-sm font-semibold">{t('alerts.saved')}</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-3">
            {/* Condition */}
            <div>
              <label className="text-[var(--fd-text-dim)] text-xs block mb-1">{t('alerts.condition')}</label>
              <select
                value={alertType}
                onChange={(e) => setAlertType(e.target.value as AlertType)}
                className="w-full bg-[var(--fd-bg-elevated)] border border-border px-3 py-1.5 text-[var(--fd-text-primary)] text-sm focus:outline-none focus:bg-[var(--fd-bg-input-focus)] transition-colors"
              >
                {ALERT_TYPES.map((at) => (
                  <option key={at} value={at}>{t(`alerts.type_${at}`)}</option>
                ))}
              </select>
            </div>

            {/* Threshold row */}
            <div>
              <label className="text-[var(--fd-text-dim)] text-xs block mb-1">
                {isPct(alertType) ? t('alerts.thresholdPct') : `${t('alerts.thresholdPrice')} (${currency.code})`}
              </label>
              <div className="flex">
                {!isPct(alertType) && (
                  <select
                    value={currency.code}
                    onChange={(e) => setCurrency(CURRENCIES.find(c => c.code === e.target.value) || CURRENCIES[0])}
                    className="bg-[var(--fd-bg)] border border-r-0 border-border px-2 py-1.5 text-[var(--fd-text-dim)] text-sm focus:outline-none focus:bg-[var(--fd-bg-input-focus)] transition-colors"
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c.code} value={c.code}>{c.symbol} {c.code}</option>
                    ))}
                  </select>
                )}
                <input
                  type="number"
                  step="any"
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value)}
                  placeholder={isPct(alertType) ? '5' : '0.00'}
                  className="flex-1 bg-[var(--fd-bg-elevated)] border border-border px-3 py-1.5 text-[var(--fd-text-primary)] placeholder-[var(--fd-text-faint)] text-sm focus:outline-none focus:bg-[var(--fd-bg-input-focus)] transition-colors"
                  autoFocus
                />
              </div>
            </div>

            {error && <p className="text-red-400 text-xs">{error}</p>}

            <div className="flex gap-2 pt-1">
              <button
                type="submit"
                disabled={saving}
                className="flex-1 py-1.5 bg-[var(--fd-bg-input-focus)] border border-[var(--color-accent)] text-[var(--color-accent)] text-sm font-medium hover:bg-[var(--fd-bg-hover)] transition-colors disabled:opacity-50"
              >
                {saving ? t('alerts.saving') : t('alerts.add')}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 border border-border text-[var(--fd-text-dim)] text-sm hover:text-[var(--fd-text-primary)] hover:border-[var(--fd-rule-strong)] transition-colors"
              >
                {t('alerts.cancel')}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
