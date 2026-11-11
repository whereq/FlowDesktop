export interface Currency { code: string; symbol: string }

export const CURRENCIES: Currency[] = [
  { code: 'USD', symbol: '$'   },
  { code: 'CNY', symbol: '¥'  },
  { code: 'HKD', symbol: 'HK$' },
  { code: 'JPY', symbol: '¥'  },
  { code: 'CAD', symbol: 'C$'  },
  { code: 'SGD', symbol: 'S$'  },
  { code: 'TWD', symbol: 'NT$' },
  { code: 'KRW', symbol: '₩'  },
]

const MAP: Record<string, Currency> = {
  NYSE: CURRENCIES[0], NYQ: CURRENCIES[0], NMS: CURRENCIES[0],
  NGM: CURRENCIES[0],  NGS: CURRENCIES[0], NCM: CURRENCIES[0],
  BTS: CURRENCIES[0],  NASDAQ: CURRENCIES[0],
  SSE: CURRENCIES[1],  SZSE: CURRENCIES[1],
  SHH: CURRENCIES[1],  SHZ: CURRENCIES[1],
  HK:  CURRENCIES[2],  HKG: CURRENCIES[2],
  JPX: CURRENCIES[3],  TSE: CURRENCIES[3],
  TSX: CURRENCIES[4],  TOR: CURRENCIES[4],
  SGX: CURRENCIES[5],  SES: CURRENCIES[5],
  TAI: CURRENCIES[6],  TW:  CURRENCIES[6],
  KSC: CURRENCIES[7],  KS:  CURRENCIES[7],
}

export function currencyForExchange(exchange: string | null | undefined): Currency {
  return (exchange && MAP[exchange]) || CURRENCIES[0]
}
