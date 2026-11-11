import { useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { streamStockAnalysis } from '../api/client'
import i18n from '../i18n'

interface Props {
  symbol: string
}

type State = 'idle' | 'loading' | 'streaming' | 'done' | 'error'

export default function AiAnalysisPanel({ symbol }: Props) {
  const [state, setState] = useState<State>('idle')
  const [content, setContent] = useState('')
  const [error, setError] = useState('')

  const run = useCallback(() => {
    setState('loading')
    setContent('')
    setError('')

    streamStockAnalysis(
      symbol,
      i18n.language,
      (delta: string) => {
        setState('streaming')
        setContent(prev => prev + delta)
      },
      (err) => {
        setError(err)
        setState('error')
      },
      () => {
        setState('done')
      },
    )
  }, [symbol])

  if (state === 'idle') {
    return (
      <div className="rounded-lg border border-border bg-surface-card p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-[#6b7280]">
            FlowDesktop AI Analysis
          </span>
        </div>
        <p className="text-sm text-[#6b7280] mb-3">
          Get an AI-generated reading of {symbol}'s price action and fundamentals, powered by FlowDesktop's collected data.
        </p>
        <button
          onClick={run}
          className="flex items-center gap-2 px-4 py-2 rounded bg-[var(--color-accent)] hover:bg-[#106ebe] text-white text-sm font-medium transition-colors"
        >
          <SparkleIcon />
          Analyze {symbol}
        </button>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border bg-surface-card p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-semibold uppercase tracking-widest text-[#6b7280]">
          FlowDesktop AI Analysis — {symbol}
        </span>
        <button
          onClick={() => setState('idle')}
          className="text-[11px] text-[#6b7280] hover:text-white transition-colors"
        >
          Reset
        </button>
      </div>

      {state === 'loading' && (
        <div className="flex items-center gap-2 text-sm text-[#6b7280] py-4">
          <LoadingDots />
          <span>Pulling FlowDesktop data and generating analysis...</span>
        </div>
      )}

      {state === 'error' && (
        <p className="text-sm text-red-400">{error || 'Analysis failed. Please try again.'}</p>
      )}

      {(state === 'streaming' || state === 'done') && content && (
        <div className="prose prose-invert prose-sm max-w-none text-[var(--fd-text-secondary)] leading-relaxed">
          <ReactMarkdown>{content}</ReactMarkdown>
          {state === 'streaming' && (
            <span className="inline-block w-1.5 h-4 bg-[var(--color-accent)] animate-pulse ml-0.5 align-middle" />
          )}
        </div>
      )}

      {state === 'done' && (
        <button
          onClick={run}
          className="mt-3 text-[11px] text-[#6b7280] hover:text-white transition-colors"
        >
          Refresh analysis
        </button>
      )}
    </div>
  )
}

function SparkleIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3 L13.5 8.5 L19 10 L13.5 11.5 L12 17 L10.5 11.5 L5 10 L10.5 8.5 Z" />
      <path d="M5 3 L5.75 5.25 L8 6 L5.75 6.75 L5 9 L4.25 6.75 L2 6 L4.25 5.25 Z" />
      <path d="M19 14 L19.75 16.25 L22 17 L19.75 17.75 L19 20 L18.25 17.75 L16 17 L18.25 16.25 Z" />
    </svg>
  )
}

function LoadingDots() {
  return (
    <span className="flex gap-1">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent)] animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </span>
  )
}
