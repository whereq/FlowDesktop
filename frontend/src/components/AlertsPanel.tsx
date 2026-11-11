import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useAlerts } from '../hooks/useStocks'
import StockSymbolInput from './StockSymbolInput'
import type { AlertType, SearchResult, UserAlert } from '../api/client'
import { CURRENCIES, currencyForExchange, type Currency } from '../utils/alertCurrency'

// ── Alert types ───────────────────────────────────────────────────────────────

const ALERT_TYPES: AlertType[] = ['price_above', 'price_below', 'change_pct_above', 'change_pct_below']

function isPctType(t: AlertType) { return t.includes('change_pct') }

// ── AlertRow ──────────────────────────────────────────────────────────────────

function AlertRow({ alert, onDelete, onRearm }: {
  alert: UserAlert
  onDelete: (id: number) => void
  onRearm: (id: number) => void
}) {
  const { t } = useTranslation()
  const isTriggered = !alert.is_active && alert.triggered_at !== null
  const isPct = isPctType(alert.alert_type)

  const thresholdDisplay = isPct
    ? `${alert.threshold > 0 ? '+' : ''}${alert.threshold}%`
    : `${alert.threshold.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  return (
    <div className={`flex items-center justify-between gap-3 px-4 py-2.5 border-b border-border last:border-b-0 ${isTriggered ? 'opacity-60' : ''}`}>
      <div className="flex items-center gap-3 min-w-0">
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${isTriggered ? 'bg-amber-400' : 'bg-emerald-500'}`} />
        <div className="min-w-0">
          <p className="text-[var(--fd-text-primary)] text-sm font-semibold leading-tight">{alert.symbol}</p>
          <p className="text-[var(--fd-text-dim)] text-xs mt-0.5">
            {t(`alerts.type_${alert.alert_type}`)} <span className="text-[var(--fd-text-secondary)]">{thresholdDisplay}</span>
          </p>
          {isTriggered && alert.triggered_at && (
            <p className="text-amber-400/80 text-[10px] mt-0.5">
              {t('alerts.triggeredAt')} {new Date(alert.triggered_at).toLocaleString()}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-1 flex-shrink-0">
        {isTriggered && (
          <button
            onClick={() => onRearm(alert.id)}
            className="text-[10px] px-2 py-0.5 border border-[#555] text-[var(--fd-text-dim)] hover:text-[var(--fd-text-primary)] hover:border-[var(--fd-rule-strong)] transition-colors"
          >
            {t('alerts.rearm')}
          </button>
        )}
        <button
          onClick={() => onDelete(alert.id)}
          className="text-[var(--fd-text-faint)] hover:text-red-400 transition-colors p-1"
          aria-label={t('alerts.delete')}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AlertsPanel() {
  const { t } = useTranslation()
  const { data: alerts = [], isLoading, createAlert, deleteAlert, rearmAlert } = useAlerts()

  const [symbol, setSymbol]       = useState('')
  const [alertType, setAlertType] = useState<AlertType>('price_above')
  const [threshold, setThreshold] = useState('')
  const [currency, setCurrency]   = useState<Currency>(CURRENCIES[0])
  const [saving, setSaving]       = useState(false)
  const [error, setError]         = useState<string | null>(null)

  // Auto-detect currency when user picks a stock from the dropdown
  const handleStockSelect = (result: SearchResult) => {
    setCurrency(currencyForExchange(result.exchange))
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const sym = symbol.toUpperCase().trim()
    const val = parseFloat(threshold)
    if (!sym || isNaN(val)) {
      setError(t('alerts.invalidInput'))
      return
    }
    setSaving(true)
    setError(null)
    try {
      await createAlert(sym, alertType, val)
      setSymbol('')
      setThreshold('')
    } catch {
      setError(t('alerts.saveError'))
    } finally {
      setSaving(false)
    }
  }

  const isPct = isPctType(alertType)
  const active   = alerts.filter((a) => a.is_active)
  const triggered = alerts.filter((a) => !a.is_active)

  return (
    <div className="space-y-6">
      {/* ── Create form ── */}
      <div className="bg-surface-card border border-border p-4">
        <h3 className="text-[var(--fd-text-secondary)] text-sm font-semibold tracking-widest uppercase mb-4">
          {t('alerts.newAlert')}
        </h3>

        <form onSubmit={handleSubmit} className="flex flex-wrap gap-x-3 gap-y-3 items-end">

          {/* Symbol / Stock Name */}
          <div className="flex flex-col gap-1">
            <label className="text-[var(--fd-text-dim)] text-xs">{t('alerts.symbolLabel')}</label>
            <StockSymbolInput
              value={symbol}
              onChange={setSymbol}
              onSelect={handleStockSelect}
              placeholder={t('alerts.symbolPlaceholder')}
              className="w-64"
            />
          </div>

          {/* Condition */}
          <div className="flex flex-col gap-1">
            <label className="text-[var(--fd-text-dim)] text-xs">{t('alerts.condition')}</label>
            <select
              value={alertType}
              onChange={(e) => setAlertType(e.target.value as AlertType)}
              className="bg-[var(--fd-bg-elevated)] border border-border px-3 py-1.5 text-[var(--fd-text-primary)] text-sm focus:outline-none focus:bg-[var(--fd-bg-input-focus)] transition-colors"
            >
              {ALERT_TYPES.map((at) => (
                <option key={at} value={at}>{t(`alerts.type_${at}`)}</option>
              ))}
            </select>
          </div>

          {/* Threshold + currency row */}
          <div className="flex flex-col gap-1">
            <label className="text-[var(--fd-text-dim)] text-xs">
              {isPct ? t('alerts.thresholdPct') : `${t('alerts.thresholdPrice')} (${currency.code})`}
            </label>
            <div className="flex">
              {/* Currency prefix — hidden for pct types */}
              {!isPct && (
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
                placeholder={isPct ? '5' : '150.00'}
                className="bg-[var(--fd-bg-elevated)] border border-border px-3 py-1.5 text-[var(--fd-text-primary)] placeholder-[#555] text-sm focus:outline-none focus:bg-[var(--fd-bg-input-focus)] transition-colors w-28"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={saving}
            className="px-4 py-1.5 bg-[var(--fd-bg-input-focus)] border border-[var(--color-accent)] text-[var(--color-accent)] text-sm font-medium hover:bg-[var(--fd-bg-hover)] transition-colors disabled:opacity-50 self-end"
          >
            {saving ? t('alerts.saving') : t('alerts.add')}
          </button>
        </form>

        {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
      </div>

      {/* ── Active alerts ── */}
      <div className="bg-surface-card border border-border">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h3 className="text-[var(--fd-text-secondary)] text-sm font-semibold tracking-widest uppercase">
            {t('alerts.active')}
          </h3>
          <span className="text-[var(--fd-text-dim)] text-xs">{active.length}</span>
        </div>
        {isLoading ? (
          <p className="text-[var(--fd-text-dim)] text-sm px-4 py-6 text-center">{t('alerts.loading')}</p>
        ) : active.length === 0 ? (
          <p className="text-[var(--fd-text-dim)] text-sm px-4 py-6 text-center">{t('alerts.noActive')}</p>
        ) : (
          active.map((a) => (
            <AlertRow key={a.id} alert={a} onDelete={deleteAlert} onRearm={rearmAlert} />
          ))
        )}
      </div>

      {/* ── Triggered alerts ── */}
      {triggered.length > 0 && (
        <div className="bg-surface-card border border-border">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <h3 className="text-[var(--fd-text-secondary)] text-sm font-semibold tracking-widest uppercase">
              {t('alerts.triggered')}
            </h3>
            <span className="text-[var(--fd-text-dim)] text-xs">{triggered.length}</span>
          </div>
          {triggered.map((a) => (
            <AlertRow key={a.id} alert={a} onDelete={deleteAlert} onRearm={rearmAlert} />
          ))}
        </div>
      )}
    </div>
  )
}
