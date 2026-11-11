import { useState, useRef, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import clsx from 'clsx'

interface ExchangeFilterProps {
  exchanges: string[]
  selected: string[]
  onToggle: (ex: string) => void
  onClear: () => void
}

/** Region grouping — ordered by popularity/trading volume within each region. */
interface RegionGroup {
  labelKey: string
  codes: string[]
}

const REGION_GROUPS: RegionGroup[] = [
  { labelKey: 'regions.northAmerica', codes: ['NYSE', 'NYQ', 'NYS', 'NMS', 'NASDAQ', 'NGM', 'NGS', 'NCM', 'TSX', 'TOR', 'BTS'] },
  { labelKey: 'regions.china',        codes: ['SSE', 'SHH', 'SZSE', 'SHZ', 'HK', 'HKG', 'TAI', 'TW'] },
  { labelKey: 'regions.asia',         codes: ['JPX', 'TSE', 'KSC', 'KS', 'SGX', 'SES'] },
  { labelKey: 'regions.indices',      codes: ['SNP', 'DJI', 'NIM', 'CXI', 'WCB'] },
]

/** Multi-select exchange dropdown grouped by region. */
export default function ExchangeFilter({ exchanges, selected, onToggle, onClear }: ExchangeFilterProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [expandedRegions, setExpandedRegions] = useState<Set<string>>(new Set())
  const ref = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Build visible groups: only show exchanges that exist in the available list
  const visibleGroups = useMemo(() => {
    const available = new Set(exchanges)
    return REGION_GROUPS
      .map(group => ({
        ...group,
        codes: group.codes.filter(c => available.has(c)),
      }))
      .filter(group => group.codes.length > 0)
  }, [exchanges])

  // Exchanges not in any region group (fallback)
  const ungrouped = useMemo(() => {
    const grouped = new Set(REGION_GROUPS.flatMap(g => g.codes))
    return exchanges.filter(ex => !grouped.has(ex))
  }, [exchanges])

  const toggleRegion = (labelKey: string) => {
    setExpandedRegions(prev => {
      const next = new Set(prev)
      if (next.has(labelKey)) next.delete(labelKey)
      else next.add(labelKey)
      return next
    })
  }

  const label = selected.length === 0
    ? t('filter.allExchanges')
    : selected.length === 1
    ? t('exchanges.' + selected[0])
    : `${selected.length} ${t('filter.allExchanges').split(' ')[0]}`

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={clsx(
          'shrink-0 flex items-center justify-between gap-2 px-3 py-1.5 text-sm border transition-colors min-w-[160px]',
          selected.length > 0
            ? 'bg-[var(--fd-bg-hover)] border-[var(--color-nova)] text-[var(--color-nova)] hover:bg-[var(--fd-bg-elevated)]'
            : 'bg-[var(--fd-bg-elevated)] border-border text-[var(--fd-text-secondary)] hover:border-[var(--fd-rule-strong)] hover:text-[var(--fd-text-primary)]'
        )}
      >
        {label}
        <svg className="w-3 h-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="square" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute z-50 top-full mt-1 bg-surface-card border border-border min-w-[220px] max-h-[400px] overflow-y-auto">
          {visibleGroups.map((group) => {
            const isExpanded = expandedRegions.has(group.labelKey)
            const selectedInGroup = group.codes.filter(c => selected.includes(c)).length
            return (
              <div key={group.labelKey}>
                {/* Region header */}
                <button
                  onClick={() => toggleRegion(group.labelKey)}
                  className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--fd-text-dim)] hover:text-[var(--fd-text-secondary)] hover:bg-[var(--fd-hover-bg)] border-b border-[var(--fd-rule)]"
                >
                  <span className="flex items-center gap-1.5">
                    <svg
                      className={clsx('w-3 h-3 transition-transform', isExpanded && 'rotate-90')}
                      fill="none" viewBox="0 0 24 24" stroke="currentColor"
                    >
                      <path strokeLinecap="square" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                    {t(group.labelKey)}
                  </span>
                  {selectedInGroup > 0 && (
                    <span className="text-[10px] bg-[var(--fd-bg-hover)] text-[var(--color-nova)] px-1.5 py-0.5 rounded-sm">
                      {selectedInGroup}
                    </span>
                  )}
                </button>

                {/* Exchange items */}
                {isExpanded && group.codes.map((ex) => (
                  <label
                    key={ex}
                    className="flex items-center gap-2 pl-7 pr-3 py-1.5 cursor-pointer hover:bg-surface-raised text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={selected.includes(ex)}
                      onChange={() => onToggle(ex)}
                      className="accent-[var(--color-accent)] w-3.5 h-3.5 cursor-pointer shrink-0"
                    />
                    <span className={selected.includes(ex) ? 'text-[var(--color-nova)]' : 'text-[var(--fd-text-secondary)]'}>
                      {t('exchanges.' + ex)}
                    </span>
                  </label>
                ))}
              </div>
            )
          })}

          {/* Ungrouped exchanges (if any) */}
          {ungrouped.length > 0 && (
            <div>
              <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--fd-text-dim)] border-b border-[var(--fd-rule)]">
                {t('regions.other')}
              </div>
              {ungrouped.map((ex) => (
                <label
                  key={ex}
                  className="flex items-center gap-2 pl-7 pr-3 py-1.5 cursor-pointer hover:bg-surface-raised text-sm"
                >
                  <input
                    type="checkbox"
                    checked={selected.includes(ex)}
                    onChange={() => onToggle(ex)}
                    className="accent-[var(--color-accent)] w-3.5 h-3.5 cursor-pointer shrink-0"
                  />
                  <span className={selected.includes(ex) ? 'text-[var(--color-nova)]' : 'text-[var(--fd-text-secondary)]'}>
                    {t('exchanges.' + ex)}
                  </span>
                </label>
              ))}
            </div>
          )}

          {selected.length > 0 && (
            <button
              onClick={onClear}
              className="w-full px-3 py-2 text-xs text-[var(--fd-text-dim)] hover:text-[var(--fd-text-primary)] hover:bg-surface-raised text-left border-t border-border"
            >
              {t('filter.clearAll')}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
