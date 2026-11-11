import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import Modal from '../Modal'
import { api, type SimOrder, type TradableStock } from '../../api/client'

const inputCls =
  'w-full text-xs bg-[var(--fd-bg)] border border-[var(--fd-rule)] px-2 py-1.5 text-[var(--fd-text)] focus:border-[var(--color-accent)] outline-none'

/** Reusable simulated-order ticket. Used by the Simulator page and StockDetail. */
export default function OrderTicket({
  accountId, currency, presetSymbol, initialSide = 'buy', onClose,
}: {
  accountId: number
  currency: string
  presetSymbol?: string
  initialSide?: 'buy' | 'sell'
  onClose: () => void
}) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [symbol, setSymbol] = useState((presetSymbol ?? '').toUpperCase())
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<TradableStock[]>([])
  const [side, setSide] = useState<'buy' | 'sell'>(initialSide)
  const [orderType, setOrderType] = useState<'market' | 'limit'>('market')
  const [quantity, setQuantity] = useState('')
  const [limitPrice, setLimitPrice] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<SimOrder | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!query.trim()) { setResults([]); return }
    const id = setTimeout(async () => {
      try { setResults(await api.searchTradable(accountId, query.trim())) } catch { setResults([]) }
    }, 250)
    return () => clearTimeout(id)
  }, [query, accountId])

  const submit = async () => {
    setError(''); setResult(null)
    if (!symbol.trim() || !quantity.trim()) {
      setError(t('sim.needSymbolQty', 'Enter a symbol and quantity')); return
    }
    setBusy(true)
    try {
      const o = await api.placeSimOrder(accountId, {
        symbol: symbol.trim().toUpperCase(), side, order_type: orderType,
        quantity, limit_price: orderType === 'limit' ? limitPrice : null,
        idempotency_key: crypto.randomUUID(),
      })
      setResult(o)
      qc.invalidateQueries({ queryKey: ['sim-account', accountId] })
      qc.invalidateQueries({ queryKey: ['sim-orders', accountId] })
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? t('sim.orderFailed', 'Order failed'))
    } finally { setBusy(false) }
  }

  const seg = (active: boolean) =>
    `flex-1 text-xs py-1.5 border ${active
      ? 'border-[var(--color-accent)] bg-[var(--fd-bg-elev)] text-[var(--color-accent)]'
      : 'border-[var(--fd-rule)] text-[var(--fd-text-dim)] hover:text-[var(--fd-text)]'}`

  const actions = (
    <>
      <button onClick={onClose} className="text-xs py-1.5 px-3 border border-[var(--fd-rule)] text-[var(--fd-text-dim)] hover:text-[var(--fd-text)]">
        {result ? t('common.close', 'Close') : t('common.cancel', 'Cancel')}
      </button>
      <button onClick={submit} disabled={busy}
        className="text-xs py-1.5 px-3 border border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)] disabled:opacity-50">
        {busy ? t('sim.placing', 'Placing…') : `${side === 'buy' ? t('sim.buy', 'Buy') : t('sim.sell', 'Sell')} ${currency}`}
      </button>
    </>
  )

  return (
    <Modal isOpen onClose={onClose} title={t('sim.orderTicket', 'Order ticket')} actions={actions}>
      <div className="flex flex-col gap-2.5 min-w-[280px]">
        <div className="flex gap-0">
          <button className={seg(side === 'buy')} onClick={() => setSide('buy')}>{t('sim.buy', 'Buy')}</button>
          <button className={seg(side === 'sell')} onClick={() => setSide('sell')}>{t('sim.sell', 'Sell')}</button>
        </div>

        <div className="relative">
          <input
            className={inputCls}
            placeholder={t('sim.symbolPlaceholder', 'Symbol (search…)')}
            value={symbol}
            onChange={(e) => { setSymbol(e.target.value.toUpperCase()); setQuery(e.target.value) }}
          />
          {results.length > 0 && (
            <div className="absolute z-10 left-0 right-0 mt-0.5 max-h-40 overflow-auto bg-[var(--fd-bg-panel)] border border-[var(--fd-rule)]">
              {results.map((r) => (
                <button key={r.symbol}
                  className="block w-full text-left px-2 py-1 text-[11px] text-[var(--fd-text-dim)] hover:bg-[var(--fd-bg-elev)]"
                  onClick={() => { setSymbol(r.symbol); setQuery(''); setResults([]) }}>
                  <span className="font-mono text-[var(--fd-text)]">{r.symbol}</span> · {r.name}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex gap-0">
          <button className={seg(orderType === 'market')} onClick={() => setOrderType('market')}>{t('sim.market', 'Market')}</button>
          <button className={seg(orderType === 'limit')} onClick={() => setOrderType('limit')}>{t('sim.limit', 'Limit')}</button>
        </div>

        <input className={inputCls} inputMode="numeric" placeholder={t('sim.quantity', 'Quantity (shares)')}
          value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        {orderType === 'limit' && (
          <input className={inputCls} inputMode="decimal" placeholder={t('sim.limitPrice', 'Limit price')}
            value={limitPrice} onChange={(e) => setLimitPrice(e.target.value)} />
        )}

        {error && <div className="text-[11px] text-amber-500">{error}</div>}
        {result && (
          <div className={`text-[11px] ${result.status === 'rejected' ? 'text-rose-400' : 'text-green-400'}`}>
            {result.status === 'filled'
              ? t('sim.filledAt', 'Filled at {{p}}', { p: result.avg_fill_price })
              : result.status === 'rejected'
                ? t('sim.rejected', 'Rejected: {{r}}', { r: result.reject_reason })
                : t('sim.resting', 'Order resting ({{s}})', { s: result.status })}
          </div>
        )}
      </div>
    </Modal>
  )
}
