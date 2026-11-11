import { useTranslation } from 'react-i18next'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { format, parseISO } from 'date-fns'
import type { HistoricalPrice } from '../api/client'

interface PriceChartProps {
  data: HistoricalPrice[]
  isLoading?: boolean
}

export default function PriceChart({ data, isLoading }: PriceChartProps) {
  const { t, i18n } = useTranslation()
  const locale = i18n.language === 'zh' ? 'zh-CN' : 'en-US'

  if (isLoading) {
    return (
      <div className="h-64 bg-surface-card border border-border flex items-center justify-center">
        <div className="h-6 w-6 border-2 border-[var(--color-accent)] border-t-transparent animate-spin" />
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="h-64 bg-surface-card border border-border flex items-center justify-center text-[var(--fd-text-dim)] text-sm">
        {t('stock.noHistory')}
      </div>
    )
  }

  const chartData = data.map((d) => ({
    date: d.date,
    close: d.close,
    formattedDate: format(parseISO(d.date), locale === 'zh-CN' ? 'M/d' : 'MMM d'),
  }))

  const minValue = Math.min(...chartData.map((d) => d.close || 0))
  const maxValue = Math.max(...chartData.map((d) => d.close || 0))
  const padding = (maxValue - minValue) * 0.1

  const isPositive =
    chartData.length >= 2 &&
    (chartData[chartData.length - 1].close || 0) >= (chartData[0].close || 0)

  const lineColor = isPositive ? '#3CCB7F' : '#F25B5B'

  return (
    <div className="h-64 bg-surface-card border border-border p-4" style={{ minWidth: 200, minHeight: 180 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="colorClose" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={lineColor} stopOpacity={0.2} />
              <stop offset="95%" stopColor={lineColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="formattedDate"
            stroke="var(--fd-text-faint)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            stroke="var(--fd-text-faint)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            domain={[minValue - padding, maxValue + padding]}
            tickFormatter={(value) => `$${value.toFixed(0)}`}
            width={56}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--fd-bg-panel)',
              border: '1px solid var(--fd-rule)',
              fontSize: '12px',
              color: 'var(--fd-text-secondary)',
            }}
            labelStyle={{ color: 'var(--fd-text-dim)' }}
            itemStyle={{ color: lineColor, fontWeight: '600' }}
            formatter={(value) => value == null ? ['—', t('chart.close')] : [`$${(value as number).toFixed(2)}`, t('chart.close')]}
            labelFormatter={(label) => label}
          />
          <Area
            type="monotone"
            dataKey="close"
            stroke={lineColor}
            strokeWidth={1.5}
            fill="url(#colorClose)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
