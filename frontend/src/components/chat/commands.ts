// ── Command definitions ───────────────────────────────────────────────────────

export interface Command {
  id: string
  label: string
  shortLabel: string
  description: string
  requiresSymbol?: boolean  // needs a stock symbol to run
  needsInput?: boolean      // needs extra text input (beyond symbol)
  inputPlaceholder?: string
}

export const COMMANDS: Command[] = [
  {
    id: 'analyze',
    label: 'Analyze Stock',
    shortLabel: 'Analyze',
    description: 'AI analysis — price action, technicals & fundamentals',
    requiresSymbol: true,
  },
  {
    id: 'committee',
    label: 'Investment Committee',
    shortLabel: 'Committee',
    description: 'Bull · Bear · Risk agents debate the stock',
    requiresSymbol: true,
  },
  {
    id: 'compare',
    label: 'Compare Stocks',
    shortLabel: 'Compare',
    description: 'Side-by-side comparison with another symbol',
    requiresSymbol: true,
    needsInput: true,
    inputPlaceholder: 'Symbol to compare with, e.g. MSFT',
  },
  {
    id: 'strategy',
    label: 'Strategy Builder',
    shortLabel: 'Strategy',
    description: 'Describe a strategy → AI backtests it against real data',
    requiresSymbol: true,
    needsInput: true,
    inputPlaceholder: 'e.g. Buy when RSI < 30, sell after 2 weeks',
  },
  {
    id: 'screen',
    label: 'Screen Stocks',
    shortLabel: 'Screen',
    description: 'Natural language filter across 15,000+ stocks',
    needsInput: true,
    inputPlaceholder: 'e.g. Chinese tech, market cap > $5B, down 3% today',
  },
  {
    id: 'macro',
    label: 'Macro Impact',
    shortLabel: 'Macro',
    description: 'How a macro event affects your watchlist',
    needsInput: true,
    inputPlaceholder: 'e.g. Fed rate hike 50bps, China stimulus announced',
  },
  {
    id: 'portfolio',
    label: 'Shadow Portfolio',
    shortLabel: 'Portfolio',
    description: 'Paper trade journal + AI behavioral analysis',
  },
]
