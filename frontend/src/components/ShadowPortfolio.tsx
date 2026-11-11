import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { addShadowTrade, listShadowTrades, deleteShadowTrade, type ShadowTrade } from '../api/client'
import { useLLMContext } from '../contexts/useLLMContext'

export default function ShadowPortfolio() {
  const { t } = useTranslation()
  const { runPortfolioAnalysis, streaming } = useLLMContext()

  const [trades, setTrades] = useState<ShadowTrade[]>([])
  const [loading, setLoading] = useState(true)
  const [formVisible, setFormVisible] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Form state
  const [symbol, setSymbol] = useState('')
  const [action, setAction] = useState<'buy' | 'sell'>('buy')
  const [shares, setShares] = useState('')
  const [price, setPrice] = useState('')
  const [note, setNote] = useState('')
  const [tradeDate, setTradeDate] = useState(() => new Date().toISOString().slice(0, 10))

  const fetchTrades = useCallback(async () => {
    try {
      const data = await listShadowTrades()
      setTrades(data)
    } catch {
      // silently ignore — auth may not be available yet
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTrades()
  }, [fetchTrades])

  async function handleSubmit() {
    if (!symbol.trim() || !shares || !price) return
    setSaving(true)
    setError(null)
    try {
      await addShadowTrade({
        symbol: symbol.trim().toUpperCase(),
        action,
        shares: parseFloat(shares),
        price: parseFloat(price),
        note: note.trim() || null,
        trade_date: tradeDate,
      })
      // Reset form
      setSymbol('')
      setShares('')
      setPrice('')
      setNote('')
      setFormVisible(false)
      await fetchTrades()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save trade')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteShadowTrade(id)
      setTrades(prev => prev.filter(t => t.id !== id))
    } catch {
      // noop
    }
  }

  if (loading) {
    return (
      <div className="p-4 text-xs text-[var(--fd-text-faint)] text-center">
        {t('chat.streaming', 'Loading...')}
      </div>
    )
  }

  return (
    <div className="px-3 py-2 space-y-2">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--color-accent)]">
          {t('chat.actionPortfolio', 'Shadow Portfolio')}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={runPortfolioAnalysis}
            disabled={streaming || trades.length === 0}
            className="text-[10px] px-2 py-0.5 bg-[#0d2340] border border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-accent)] hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            AI Analyze
          </button>
          <button
            type="button"
            onClick={() => setFormVisible(v => !v)}
            className="text-[10px] px-2 py-0.5 bg-[#1a2535] border border-[var(--fd-rule)] text-[var(--fd-text-secondary)] hover:bg-[var(--fd-bg-input-focus)] transition-colors"
          >
            {formVisible ? 'Cancel' : '+ Add Trade'}
          </button>
        </div>
      </div>

      {/* Add trade form */}
      {formVisible && (
        <div className="bg-[var(--fd-bg-panel)] border border-[var(--fd-rule)] p-2 space-y-1.5">
          <div className="grid grid-cols-2 gap-1.5">
            <input
              value={symbol}
              onChange={e => setSymbol(e.target.value)}
              placeholder="Symbol"
              className="bg-transparent border border-[var(--fd-rule)] text-[var(--fd-text-secondary)] text-xs px-2 py-1 focus:outline-none focus:bg-[var(--fd-bg-input-focus)]"
            />
            <div className="flex gap-1">
              {(['buy', 'sell'] as const).map(a => (
                <button
                  key={a}
                  type="button"
                  onClick={() => setAction(a)}
                  className={`flex-1 text-xs py-1 border transition-colors ${
                    action === a
                      ? a === 'buy'
                        ? 'bg-green-900/50 border-green-600 text-green-300'
                        : 'bg-red-900/50 border-red-600 text-red-300'
                      : 'border-[var(--fd-rule)] text-[var(--fd-text-faint)] hover:text-[var(--fd-text-secondary)]'
                  }`}
                >
                  {a.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            <input
              value={shares}
              onChange={e => setShares(e.target.value)}
              placeholder="Shares"
              type="number"
              min="0"
              step="any"
              className="bg-transparent border border-[var(--fd-rule)] text-[var(--fd-text-secondary)] text-xs px-2 py-1 focus:outline-none focus:bg-[var(--fd-bg-input-focus)]"
            />
            <input
              value={price}
              onChange={e => setPrice(e.target.value)}
              placeholder="Price"
              type="number"
              min="0"
              step="any"
              className="bg-transparent border border-[var(--fd-rule)] text-[var(--fd-text-secondary)] text-xs px-2 py-1 focus:outline-none focus:bg-[var(--fd-bg-input-focus)]"
            />
          </div>
          <input
            value={tradeDate}
            onChange={e => setTradeDate(e.target.value)}
            type="date"
            className="w-full bg-transparent border border-[var(--fd-rule)] text-[var(--fd-text-secondary)] text-xs px-2 py-1 focus:outline-none focus:bg-[var(--fd-bg-input-focus)]"
          />
          <input
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder="Note (optional)"
            className="w-full bg-transparent border border-[var(--fd-rule)] text-[var(--fd-text-secondary)] text-xs px-2 py-1 focus:outline-none focus:bg-[var(--fd-bg-input-focus)]"
          />
          {error && <p className="text-[10px] text-red-400">{error}</p>}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving || !symbol.trim() || !shares || !price}
            className="w-full py-1 bg-[var(--color-accent)] text-white text-xs disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : 'Save Trade'}
          </button>
        </div>
      )}

      {/* Trade list */}
      {trades.length === 0 ? (
        <p className="text-xs text-[var(--fd-text-faint)] text-center py-3">
          No trades yet. Add your first paper trade above.
        </p>
      ) : (
        <div className="space-y-1 max-h-48 overflow-y-auto thin-scrollbar-ai">
          {trades.map(trade => (
            <div
              key={trade.id}
              className="flex items-center justify-between px-2 py-1.5 bg-[var(--fd-bg-panel)] border border-[var(--fd-rule)] text-xs"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className={`text-[9px] font-bold px-1 py-0.5 ${
                  trade.action === 'buy' ? 'bg-green-900/40 text-green-400' : 'bg-red-900/40 text-red-400'
                }`}>
                  {trade.action.toUpperCase()}
                </span>
                <span className="font-semibold text-[var(--fd-text-secondary)]">{trade.symbol}</span>
                <span className="text-[var(--fd-text-faint)]">{trade.shares}@{trade.price}</span>
                {trade.note && (
                  <span className="text-[var(--fd-text-dim)] truncate text-[10px]">{trade.note}</span>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[10px] text-[var(--fd-text-dim)]">
                  {trade.trade_date.slice(0, 10)}
                </span>
                <button
                  type="button"
                  onClick={() => handleDelete(trade.id)}
                  className="text-[var(--fd-text-faint)] hover:text-red-500 transition-colors"
                  title="Delete trade"
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
