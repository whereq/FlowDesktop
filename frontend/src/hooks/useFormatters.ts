import { useTranslation } from 'react-i18next'

/**
 * Locale-aware formatters backed by the native Intl API.
 * All formatting automatically respects the current i18n language.
 */
export function useFormatters() {
  const { i18n } = useTranslation()
  const locale = i18n.language === 'zh' ? 'zh-CN' : 'en-US'

  const formatCurrency = (value: number | null | undefined): string => {
    if (value == null) return '—'
    return value.toLocaleString(locale, {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    })
  }

  const formatPercent = (value: number | null | undefined, sign = true): string => {
    if (value == null) return '—'
    const prefix = sign && value > 0 ? '+' : ''
    return `${prefix}${value.toFixed(2)}%`
  }

  const formatVolume = (value: number | null | undefined): string => {
    if (value == null) return '—'
    if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
    return value.toLocaleString(locale)
  }

  const formatMarketCap = (value: number | null | undefined): string => {
    if (value == null) return '—'
    if (value >= 1_000_000_000_000) return `$${(value / 1_000_000_000_000).toFixed(2)}T`
    if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`
    if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`
    return `$${value.toLocaleString(locale)}`
  }

  const formatNumber = (value: number | null | undefined): string => {
    if (value == null) return '—'
    return value.toLocaleString(locale)
  }

  const formatTime = (isoString: string | null | undefined): string => {
    if (isoString == null) return '—'
    return new Date(isoString).toLocaleTimeString(locale, {
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const formatDateTime = (isoString: string | null | undefined): string => {
    if (isoString == null) return '—'
    return new Date(isoString).toLocaleString(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return {
    locale,
    formatCurrency,
    formatPercent,
    formatVolume,
    formatMarketCap,
    formatNumber,
    formatTime,
    formatDateTime,
  }
}
