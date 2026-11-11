/**
 * FlowDesktop User Guide — bilingual (English / Simplified Chinese)
 * All text content is inline so the guide stays self-contained.
 */
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

// ── Types ────────────────────────────────────────────────────────────────────

interface FeatureItem { icon: string; title: string; desc: string }
interface PlanItem    { plan: string; detail: string }

interface GuideContent {
  meta: { badge: string; title: string; intro: string }
  toc: { id: string; label: string }[]
  sections: {
    gettingStarted: {
      heading: string
      intro: string
      accountHeading: string; accountBody: string
      trialHeading: string; trialBody: string
      tip: string
    }
    dashboard: {
      heading: string; intro: string
      features: FeatureItem[]
      filtersHeading: string; filtersBody: string
      viewHeading: string; viewBody: string
      tip: string
    }
    search: {
      heading: string; body: string; note: string
    }
    stockDetail: {
      heading: string; intro: string
      features: FeatureItem[]
      chartHeading: string; chartBody: string
    }
    watchlist: {
      heading: string; intro: string
      addHeading: string; addBody: string
      removeHeading: string; removeBody: string
      alertsTabHeading: string; alertsTabBody: string
      tip: string
    }
    alerts: {
      heading: string; intro: string
      createHeading: string; createBody: string
      types: string[]
      bellHeading: string; bellBody: string
      note: string
    }
    notifications: {
      heading: string; intro: string
      features: FeatureItem[]
      liveHeading: string; liveBody: string
      readHeading: string; readBody: string
    }
    sectors: {
      heading: string; intro: string
      gicsHeading: string; gicsBody: string
      themesHeading: string; themesBody: string
      relHeading: string; relBody: string
    }
    intelligence: {
      heading: string; intro: string
      newsHeading: string; newsBody: string
      signalsHeading: string; signalsBody: string
      signalItems: string[]
      sectorHeading: string; sectorBody: string
      tip: string
    }
    nova: {
      heading: string; intro: string
      openHeading: string; openBody: string
      modesHeading: string
      platformTitle: string; platformBody: string
      byokTitle: string; byokBody: string
      memoryHeading: string; memoryBody: string
      briefHeading: string; briefBody: string
    }
    novaCommands: {
      heading: string; intro: string
      features: FeatureItem[]
      focusHeading: string; focusBody: string
      toolsHeading: string; toolsBody: string
      tip: string
    }
    history: {
      heading: string; intro: string
      features: FeatureItem[]
      note: string
    }
    settings: {
      heading: string; intro: string
      displayHeading: string; displayBody: string
      dataHeading: string; dataBody: string
      aiHeading: string; aiBody1: string; aiBody2: string
      accountHeading: string; accountBody: string
    }
    pricing: {
      heading: string; intro: string
      plans: PlanItem[]
      body: string; tip: string
    }
  }
  cta: { heading: string; body: string; dashboard: string; pricing: string }
}

// ── English content ──────────────────────────────────────────────────────────

const EN: GuideContent = {
  meta: {
    badge: 'FlowDesktop · User Guide',
    title: 'Everything You Need to Know',
    intro: 'FlowDesktop is a global stock intelligence platform covering 15,000+ equities across NYSE, NASDAQ, TSX, SSE, SZSE, HKEX, JPX, SGX, TWSE, and KRX — with real-time quotes, historical prices, AI-powered signals, and NOVA, your personal financial AI assistant. This guide walks through every feature so you can get the most out of FlowDesktop from day one.',
  },
  toc: [
    { id: 'getting-started',  label: '1. Getting Started' },
    { id: 'dashboard',        label: '2. Dashboard' },
    { id: 'search',           label: '3. Stock Search' },
    { id: 'stock-detail',     label: '4. Stock Detail' },
    { id: 'watchlist',        label: '5. Watchlist' },
    { id: 'alerts',           label: '6. Price Alerts' },
    { id: 'notifications',    label: '7. Notification Centre' },
    { id: 'sectors',          label: '8. Sectors' },
    { id: 'intelligence',     label: '9. Market Intelligence' },
    { id: 'nova',             label: '10. NOVA AI Assistant' },
    { id: 'nova-commands',    label: '11. NOVA Commands' },
    { id: 'history',          label: '12. Conversation History' },
    { id: 'settings',         label: '13. Settings' },
    { id: 'pricing',          label: '14. Plans & Pricing' },
  ],
  sections: {
    gettingStarted: {
      heading: '1. Getting Started',
      intro: 'FlowDesktop is free to explore as a guest, but you need an account to access the full market, your personal watchlist, AI assistant, and price alerts.',
      accountHeading: 'Creating an account',
      accountBody: 'Click Sign Up in the top-right corner (or the user menu on mobile). You will be redirected to our secure sign-in portal. Fill in your name, email address, and a password. Once registered, sign in with the same credentials.',
      trialHeading: 'Free trial',
      trialBody: 'Every new account receives a free trial: 10 AI messages OR 7 days from your first message — whichever comes first. After the trial ends, market data (quotes, charts, watchlist, alerts) remains fully accessible; only NOVA AI responses are gated. See Plans & Pricing to upgrade.',
      tip: 'You can check your remaining trial quota at any time in Settings → AI Assistant or via the quota bar at the bottom of the NOVA chat panel.',
    },
    dashboard: {
      heading: '2. Dashboard',
      intro: 'The Dashboard is your real-time market overview — available at flowdesktop.local. It is the first page you see after signing in and updates automatically every few minutes.',
      features: [
        { icon: '📊', title: 'Market Indices',    desc: 'S&P 500, Dow Jones, NASDAQ Composite, and Russell 2000 — current price and daily change.' },
        { icon: '🚀', title: 'Top Gainers',        desc: 'Stocks with the largest positive % change today, refreshed in real time.' },
        { icon: '📉', title: 'Top Losers',         desc: 'Stocks with the steepest decline today — useful for spotting distress or opportunity.' },
        { icon: '🌐', title: 'Sector Sentiment',   desc: "AI-aggregated sentiment score per GICS sector based on today's news signals." },
        { icon: '📋', title: 'Stock Table',        desc: 'Full sortable table of all stocks. Filter by exchange, sector, or search by name/symbol.' },
        { icon: '🌅', title: 'Morning Brief',      desc: "NOVA's AI-generated daily summary — market snapshot, key movers, and macro context." },
      ],
      filtersHeading: 'Exchange & sector filters',
      filtersBody: 'Use the filter bar above the stock table to narrow by exchange (NYSE, NASDAQ, TSX, SSE, SZSE, HKEX, JPX, SGX, TWSE, KRX) or by GICS sector. Multiple filters can be combined. Click Clear all to reset.',
      viewHeading: 'Table view vs. card view',
      viewBody: 'Toggle between a compact table layout and a larger card grid using the view switcher buttons on the right side of the filter bar. Card view is better for a quick visual scan; table view shows more columns at once.',
      tip: 'Click the ✦ star icon on any stock row to set that stock as the "focused symbol" for NOVA commands. All subsequent AI commands run against that symbol automatically.',
    },
    search: {
      heading: '3. Stock Search',
      body: 'The search bar in the top navigation accepts both ticker symbols (e.g. AAPL, 600519.SS, 9988.HK) and company names (e.g. "Apple", "Alibaba", "Toyota"). Results appear as you type. Click a result to open the Stock Detail page.',
      note: 'Search requires a signed-in account — guest users see a "Sign in to search" prompt.',
    },
    stockDetail: {
      heading: '4. Stock Detail',
      intro: "Navigate to any stock's detail page by clicking its row in the dashboard table or by searching for its symbol. The URL follows the pattern /stock/AAPL.",
      features: [
        { icon: '📈', title: 'Interactive Price Chart', desc: 'Candlestick / line chart with selectable time ranges: 1W, 1M, 3M, 6M, 1Y. Hover to see OHLCV data.' },
        { icon: '🏢', title: 'Company Info',            desc: 'Exchange, sector, industry, and market capitalisation.' },
        { icon: '💹', title: 'Trading Info',            desc: 'Current price, daily change %, volume, and last-updated timestamp.' },
        { icon: '🔗', title: 'Related Stocks',          desc: 'Correlation-based peer stocks in the same sector — useful for comparative analysis.' },
        { icon: '🔔', title: 'Set Alert',               desc: 'One-click price alert button — opens the alert modal pre-filled with the current symbol.' },
        { icon: '★',  title: 'Watchlist Toggle',        desc: 'Add or remove the stock from your watchlist directly from the detail page.' },
      ],
      chartHeading: 'Chart time ranges',
      chartBody: 'Use the 1W / 1M / 3M / 6M / 1Y buttons above the chart to switch the displayed period. Data comes from FlowDesktop\'s historical price database, which is updated daily.',
    },
    watchlist: {
      heading: '5. Watchlist',
      intro: 'Your watchlist is a personalised list of stocks you want to monitor. Access it via the Watchlist link in the top navigation. It is only available to signed-in users.',
      addHeading: 'Adding stocks',
      addBody: 'Type a symbol in the Add symbol field and press Enter or click Add. You can also click the bookmark icon on any stock row in the dashboard or detail page. Click Add Popular Stocks to seed your list with well-known symbols (AAPL, TSLA, NVDA, etc.) if you\'re getting started.',
      removeHeading: 'Removing stocks',
      removeBody: 'Hover over a stock in your watchlist and click the remove icon, or toggle the bookmark icon on any stock row. Removal is instant.',
      alertsTabHeading: 'Price Alerts tab',
      alertsTabBody: 'The Watchlist page has two tabs: Watchlist and Alerts. Switch to the Alerts tab to manage all your price alerts in one place (see Section 6 below).',
      tip: 'Stocks in your watchlist are automatically included in NOVA\'s context — so when you open the AI chat, NOVA already knows which stocks you\'re watching.',
    },
    alerts: {
      heading: '6. Price Alerts',
      intro: 'Price alerts notify you when a stock crosses a threshold you define. Alerts are monitored continuously throughout market hours and delivered via the in-app notification bell.',
      createHeading: 'Creating an alert',
      createBody: 'Go to Watchlist → Alerts tab → New Alert. You can also click the bell icon on any stock row. Choose:',
      types: [
        'Price ≥ — fires when the price rises to or above your target',
        'Price ≤ — fires when the price falls to or below your target',
        'Change % ≥ — fires when the daily change % exceeds a positive threshold',
        'Change % ≤ — fires when the daily change % falls below a negative threshold',
      ],
      bellHeading: 'Alert bell (header)',
      bellBody: 'The amber bell icon in the header shows how many of your alerts have triggered. Click it to see which alerts fired, when they fired, and to re-arm or delete them. Re-arming resets the alert to active so it can fire again.',
      note: 'Each (symbol, condition type) pair supports one alert at a time — e.g. you can have one "Price ≥" and one "Price ≤" for the same symbol, but not two "Price ≥" alerts.',
    },
    notifications: {
      heading: '7. Notification Centre',
      intro: 'The cyan bell icon in the header is the Notification Centre — a real-time stream of in-app events delivered without any page refresh.',
      features: [
        { icon: '🔔', title: 'Alert Triggered', desc: 'A price or change-% alert you set has fired. Tap to see the symbol and threshold.' },
        { icon: '📊', title: 'Volume Spike',    desc: "A stock in your watchlist is showing unusually high trading volume compared to its recent history." },
        { icon: '📰', title: 'News Signal',     desc: "NOVA's AI has extracted a high-confidence signal from breaking news for a watchlisted symbol." },
        { icon: '🔴', title: 'Sentiment Shift', desc: 'Reserved for future use — significant sentiment direction changes.' },
      ],
      liveHeading: 'Real-time delivery',
      liveBody: 'Notifications are pushed to your browser instantly over a live connection. The green dot in the notification dropdown header indicates the connection is active. If it appears grey, it is temporarily reconnecting — no action needed.',
      readHeading: 'Mark as read',
      readBody: 'Click the checkmark on any notification to mark it read, or use Mark all read at the top of the dropdown. Unread notifications are counted on the badge. Notifications persist across sessions so you never miss an event that arrived while you were offline.',
    },
    sectors: {
      heading: '8. Sectors',
      intro: 'The Sectors page (auth required) gives you a macro view of market structure — navigate to it from the top nav.',
      gicsHeading: 'GICS Sectors',
      gicsBody: 'All stocks are classified by the Global Industry Classification Standard (GICS). Each sector card shows the number of tracked stocks, an AI-generated sentiment score, and a list of the top stocks by market cap. Click a sector to filter the dashboard to that sector only.',
      themesHeading: 'Trending AI Themes',
      themesBody: 'Below the GICS sectors, FlowDesktop surfaces dynamic themes — cross-sector narratives that NOVA identifies from recent news and signals (e.g. "AI Infrastructure Build-out", "Rate Sensitivity", "China Recovery Trade"). Each theme shows related stocks and a brief narrative.',
      relHeading: 'Stock Relationships',
      relBody: 'Within each sector, FlowDesktop identifies peer stocks based on market behaviour. Related stocks appear on the Stock Detail page so you can quickly find comparable instruments.',
    },
    intelligence: {
      heading: '9. Market Intelligence',
      intro: "The Intel page (auth required) is FlowDesktop's AI-curated news and signal feed — updated continuously throughout the trading day. Navigate to it from the top nav.",
      newsHeading: 'News tab',
      newsBody: 'Headlines curated from a wide range of global financial news sources, exchange filings, and community feeds. Each headline shows the source, timestamp, and a relevance badge.',
      signalsHeading: 'Signals tab',
      signalsBody: 'Every news item is processed by NOVA to produce a structured market signal with:',
      signalItems: [
        'Signal type — earnings, macro, regulatory, geopolitical, sector, etc.',
        'Sentiment — −1.0 (very bearish) to +1.0 (very bullish)',
        'Confidence — how certain the model is in its reading',
        'Impact horizon — immediate / short-term / medium-term / long-term',
        'Symbols impacted — specific tickers identified as affected',
      ],
      sectorHeading: 'Sector Intel tab',
      sectorBody: 'Daily AI-generated sector narratives that synthesise all signals for a given GICS sector into a concise outlook — bullish/bearish/neutral stance, key drivers, and notable stocks.',
      tip: 'High-confidence signals for symbols in your watchlist are automatically pushed to your Notification Centre as News Signal alerts.',
    },
    nova: {
      heading: '10. NOVA AI Assistant',
      intro: "NOVA (Networked Observational Value Analyst) is FlowDesktop's built-in AI financial assistant. It has direct access to your watchlist, live quotes, historical price data, and sector intelligence — so its answers are grounded in real data, not just general knowledge.",
      openHeading: 'Opening the chat panel',
      openBody: 'Click the ✦ NOVA floating button at the bottom-right of the Dashboard or Watchlist page. The chat panel slides in from the right without leaving the page. It is available on the Dashboard and Watchlist pages only (where market data context is richest).',
      modesHeading: 'AI provider modes',
      platformTitle: 'FlowDesktop AI (platform mode)',
      platformBody: 'Fully managed — no API key or setup needed. FlowDesktop handles everything in the background. Counts against your plan quota.',
      byokTitle: 'Use My Own Key (BYOK)',
      byokBody: 'Connect your own OpenAI, Anthropic, Google, DeepSeek, Qwen, or MiniMax key. Unlimited usage — billed directly to your provider account. No FlowDesktop quota used.',
      memoryHeading: 'Cross-session memory',
      memoryBody: 'NOVA remembers facts you share across conversations. If you tell NOVA your risk tolerance, preferred exchanges, investment horizon, or portfolio style, it saves those as memories and personalises every future response automatically. You can view and delete your saved memories via Settings.',
      briefHeading: 'Morning Brief',
      briefBody: "Each morning NOVA generates a personalised market brief based on your watchlist — key overnight moves, macro headlines, and sector outlook. It appears at the top of the Dashboard and can be regenerated by opening the chat panel.",
    },
    novaCommands: {
      heading: '11. NOVA Commands',
      intro: 'Open the Command Palette by clicking the ⌘ icon inside the chat panel, or type / to search commands. You can also type naturally and NOVA will infer the right analysis mode.',
      features: [
        { icon: '📈', title: 'Analyze Stock',        desc: "Deep analysis of a symbol — price action, trend, technical indicators, fundamental highlights, and NOVA's verdict." },
        { icon: '⚖️', title: 'Investment Committee', desc: 'Three AI agents (Bull, Bear, Risk) debate the stock from opposing perspectives and reach a committee verdict.' },
        { icon: '🔄', title: 'Compare Stocks',       desc: 'Side-by-side comparison of two or more symbols — performance, valuation, momentum, and sector context.' },
        { icon: '🌐', title: 'Macro Impact',         desc: 'Describe a macro event (e.g. "Fed rate hike 50bps") and NOVA maps its likely impact to each stock in your watchlist.' },
        { icon: '🧪', title: 'Strategy Builder',     desc: 'Describe an entry/exit strategy in plain language and NOVA back-tests it against historical price data.' },
        { icon: '🔍', title: 'Screen Stocks',        desc: 'Natural language stock screener across 15,000+ stocks. E.g. "Chinese tech, market cap > $5B, down 3% today".' },
        { icon: '💼', title: 'Shadow Portfolio',     desc: "Paper-trade journal. Log virtual trades and ask NOVA to analyse your portfolio's performance and behavioural patterns." },
        { icon: '📊', title: 'Sector Analysis',      desc: 'Ask NOVA for an outlook on any GICS sector — sentiment, top movers, and key risks.' },
      ],
      focusHeading: 'Focused symbol',
      focusBody: 'Click the ✦ icon on any stock row to set that stock as the active symbol. Symbol-specific commands (Analyze, Committee, Compare, Strategy) will run immediately without prompting you to type a ticker.',
      toolsHeading: 'Live data lookups',
      toolsBody: 'When NOVA needs live data it doesn\'t have in context, it queries FlowDesktop\'s market data systems in real time. You will see a brief "Fetching data…" indicator while this happens. The final response is always grounded in fresh data.',
      tip: 'NOVA can look up the latest data for virtually any valid stock symbol — just ask, even if you\'ve never added it to your watchlist.',
    },
    history: {
      heading: '12. Conversation History',
      intro: 'All NOVA conversations are saved locally in your browser — they never leave your device. Access your full history via History in the top nav (auth required).',
      features: [
        { icon: '🗂️', title: 'Browse conversations', desc: 'Scroll through all past sessions, sorted by most recent. Each entry shows the first message and message count.' },
        { icon: '🔍', title: 'Search',               desc: 'Full-text search across all conversation content — find any past analysis instantly.' },
        { icon: '★',  title: 'Favourites',           desc: 'Star important conversations to pin them to the Favourites filter.' },
        { icon: '📋', title: 'Copy as text',         desc: 'Export any conversation as plain text for notes or reports.' },
        { icon: '💾', title: 'Export as JSON',       desc: 'Download the raw conversation JSON for programmatic use.' },
        { icon: '↗️', title: 'Open in chat',         desc: 'Reopen any past conversation in the live chat panel to continue the discussion.' },
      ],
      note: "Because history is stored locally in your browser, it is device-specific. Clearing browser data will erase conversation history. Use Export as JSON to back up important sessions.",
    },
    settings: {
      heading: '13. Settings',
      intro: 'Access Settings from the user menu (top-right avatar). All changes are saved to your account profile.',
      displayHeading: 'Display',
      displayBody: 'Language — switch between English and Simplified Chinese. More languages coming.\nTable Density — Normal or Compact row spacing in the stock table.',
      dataHeading: 'Data',
      dataBody: 'Market Indices and Top Gainers / Losers — toggle these dashboard widgets on or off.\nDefault Exchange / Currency / Timezone — personalise how data is displayed.',
      aiHeading: 'AI Assistant',
      aiBody1: 'Switch between FlowDesktop AI (managed, quota-counted) and Use My Own Key (BYOK, unlimited). In BYOK mode, select your provider and paste your API key — it is stored securely in your browser only and never sent to FlowDesktop servers.',
      aiBody2: 'Use the Validate button to confirm your key is valid before saving. The quota bar shows your remaining free trial messages.',
      accountHeading: 'Account',
      accountBody: 'Update your display name, email, avatar (JPG or PNG, max 16 KB), and bio. Changes are synced to your account profile.',
    },
    pricing: {
      heading: '14. Plans & Pricing',
      intro: 'All market data features (quotes, charts, watchlist, sectors, intelligence) are free for all users. Only NOVA AI responses are gated by plan.',
      plans: [
        { plan: 'Free Trial', detail: '10 AI messages OR 7 days — whichever comes first. No credit card required.' },
        { plan: 'BYOK',       detail: 'Unlimited AI with your own API key. Full market data. FlowDesktop AI not included.' },
        { plan: 'Basic',      detail: '200 AI messages / month. Full market data, stock analysis & comparison.' },
        { plan: 'Pro',        detail: '1,000 AI messages / month. All Basic features + advanced analysis & priority support.' },
        { plan: 'Unlimited',  detail: 'Unlimited AI messages. All Pro features + dedicated support.' },
      ],
      body: 'Visit the Pricing page to compare plans and upgrade. Payment is handled securely via Stripe. After a successful payment, your account is automatically upgraded — no manual steps required.',
      tip: 'Questions about team or enterprise plans? Use the feedback link at the bottom of the Pricing page to get in touch.',
    },
  },
  cta: {
    heading: 'Ready to dive in?',
    body: 'Start with the Dashboard, add a few stocks to your Watchlist, then open NOVA and ask it to analyze your portfolio.',
    dashboard: 'Go to Dashboard',
    pricing:   'View Pricing',
  },
}

// ── Chinese content ──────────────────────────────────────────────────────────

const ZH: GuideContent = {
  meta: {
    badge: 'FlowDesktop · 用户指南',
    title: '全功能使用指南',
    intro: 'FlowDesktop 是覆盖全球 15,000+ 股票的智能投资平台，涵盖纽交所、纳斯达克、多伦多交易所、上交所、深交所、港交所、东京交易所、新交所、台交所和韩交所，提供实时行情、历史价格、AI 驱动的市场信号，以及您的私人 AI 财务助手 NOVA。本指南将带您系统了解 FlowDesktop 的每一项功能，助您从第一天起就充分发挥平台价值。',
  },
  toc: [
    { id: 'getting-started',  label: '1. 快速入门' },
    { id: 'dashboard',        label: '2. 行情仪表盘' },
    { id: 'search',           label: '3. 股票搜索' },
    { id: 'stock-detail',     label: '4. 个股详情' },
    { id: 'watchlist',        label: '5. 自选股' },
    { id: 'alerts',           label: '6. 价格预警' },
    { id: 'notifications',    label: '7. 通知中心' },
    { id: 'sectors',          label: '8. 板块分析' },
    { id: 'intelligence',     label: '9. 市场情报' },
    { id: 'nova',             label: '10. NOVA AI 助手' },
    { id: 'nova-commands',    label: '11. NOVA 命令' },
    { id: 'history',          label: '12. 对话历史' },
    { id: 'settings',         label: '13. 设置' },
    { id: 'pricing',          label: '14. 套餐与定价' },
  ],
  sections: {
    gettingStarted: {
      heading: '1. 快速入门',
      intro: '游客可免费浏览 FlowDesktop 的公开内容，但注册账号后才能访问完整行情、自选股、AI 助手和价格预警等功能。',
      accountHeading: '创建账号',
      accountBody: '点击右上角的「注册」按钮（移动端在用户菜单中）。页面将跳转至我们安全的登录门户，填写姓名、邮箱和密码即可完成注册。注册后使用相同凭据登录。',
      trialHeading: '免费试用',
      trialBody: '每个新账号均可享受免费试用：10 条 AI 消息或 7 天（以先到期者为准）。试用结束后，行情数据、K 线图、自选股、价格预警等功能仍可正常使用，仅 NOVA AI 回复功能受限。如需继续使用，请前往「套餐与定价」页面升级。',
      tip: '您可随时在「设置 → AI 助手」或 NOVA 聊天面板底部的配额栏查看剩余试用次数。',
    },
    dashboard: {
      heading: '2. 行情仪表盘',
      intro: '仪表盘是您的实时市场总览页面，访问地址为 flowdesktop.local。登录后即呈现此页，每隔几分钟自动刷新数据。',
      features: [
        { icon: '📊', title: '市场指数',   desc: '标普 500、道琼斯、纳斯达克综合指数、罗素 2000 — 实时价格与当日涨跌。' },
        { icon: '🚀', title: '领涨榜',     desc: '当日涨幅最大的股票，实时更新。' },
        { icon: '📉', title: '领跌榜',     desc: '当日跌幅最深的股票 — 便于发现超跌或抄底机会。' },
        { icon: '🌐', title: '板块情绪',   desc: '基于当日新闻信号，AI 聚合生成各 GICS 板块的情绪评分。' },
        { icon: '📋', title: '股票列表',   desc: '完整的可排序股票表格，可按交易所、板块筛选，或按名称/代码搜索。' },
        { icon: '🌅', title: '每日简报',   desc: 'NOVA AI 生成的每日市场摘要 — 行情快照、主要涨跌股和宏观背景。' },
      ],
      filtersHeading: '交易所与板块筛选',
      filtersBody: '使用股票列表上方的筛选栏，按交易所（NYSE、NASDAQ、TSX、SSE、SZSE、HKEX、JPX、SGX、TWSE、KRX）或 GICS 板块进行筛选，可多条件组合。点击「清除全部」重置筛选条件。',
      viewHeading: '表格视图与卡片视图',
      viewBody: '通过筛选栏右侧的视图切换按钮，在紧凑表格和大卡片两种布局间切换。卡片视图便于快速浏览，表格视图可展示更多列数据。',
      tip: '点击任意股票行上的 ✦ 图标，将该股票设为 NOVA 命令的「焦点股票」。后续所有 AI 命令将自动针对该股票执行。',
    },
    search: {
      heading: '3. 股票搜索',
      body: '顶部导航栏的搜索框支持输入股票代码（如 AAPL、600519.SS、9988.HK）和公司名称（如"苹果"、"阿里巴巴"、"丰田"）。输入时即时显示结果，点击结果项进入个股详情页。',
      note: '搜索功能需要登录账号 — 游客将看到「请登录后搜索」的提示。',
    },
    stockDetail: {
      heading: '4. 个股详情',
      intro: '在仪表盘列表中点击股票行，或通过搜索找到股票代码，即可进入个股详情页。页面 URL 格式为 /stock/AAPL。',
      features: [
        { icon: '📈', title: '交互式价格图表', desc: 'K 线图 / 折线图，支持选择时间区间：1周、1月、3月、6月、1年。悬停可查看 OHLCV 数据。' },
        { icon: '🏢', title: '公司信息',       desc: '交易所、板块、行业、市值。' },
        { icon: '💹', title: '交易数据',       desc: '当前价格、当日涨跌幅、成交量、数据更新时间。' },
        { icon: '🔗', title: '相关股票',       desc: '同板块内基于价格相关性计算出的同类股票 — 便于横向比较分析。' },
        { icon: '🔔', title: '设置预警',       desc: '一键添加价格预警按钮 — 打开预警弹窗并自动填入当前股票代码。' },
        { icon: '★',  title: '自选股切换',     desc: '直接在详情页将该股票加入或移出自选股。' },
      ],
      chartHeading: '图表时间区间',
      chartBody: '使用图表上方的 1周 / 1月 / 3月 / 6月 / 1年 按钮切换显示时段。数据来自 FlowDesktop 历史价格数据库，每日更新。',
    },
    watchlist: {
      heading: '5. 自选股',
      intro: '自选股是您个人定制的股票监控列表。通过顶部导航栏的「自选」进入，仅对已登录用户开放。',
      addHeading: '添加股票',
      addBody: '在「添加代码」输入框中输入股票代码，按 Enter 键或点击「添加」按钮即可。也可点击仪表盘或详情页任意股票行上的书签图标快速添加。初次使用时，点击「添加热门股票」可一键加入 AAPL、TSLA、NVDA 等知名股票。',
      removeHeading: '移除股票',
      removeBody: '将鼠标悬停在自选股列表中的股票上，点击移除图标；或再次点击任意股票行上的书签图标即可移除，操作立即生效。',
      alertsTabHeading: '价格预警标签',
      alertsTabBody: '自选股页面包含两个标签：「自选股」和「预警」。切换到预警标签，可在同一页面统一管理所有价格预警（详见第 6 节）。',
      tip: 'NOVA 会自动将您的自选股纳入对话上下文 — 打开 AI 聊天时，NOVA 已知道您正在关注哪些股票。',
    },
    alerts: {
      heading: '6. 价格预警',
      intro: '价格预警在股票突破您设定的阈值时发出通知。预警在交易时段内持续自动监测，并通过应用内通知铃推送。',
      createHeading: '创建预警',
      createBody: '进入「自选股 → 预警标签 → 新建预警」。也可直接点击任意股票行上的铃铛图标。选择触发条件：',
      types: [
        '价格 ≥ — 当价格上涨至或超过目标值时触发',
        '价格 ≤ — 当价格下跌至或低于目标值时触发',
        '涨跌幅 % ≥ — 当当日涨跌幅超过正阈值时触发',
        '涨跌幅 % ≤ — 当当日涨跌幅低于负阈值时触发',
      ],
      bellHeading: '预警铃铛（顶栏）',
      bellBody: '顶栏中的琥珀色铃铛图标显示已触发的预警数量。点击可查看哪些预警已触发、触发时间，以及重新激活或删除预警。重新激活后，预警恢复为活跃状态，可再次触发。',
      note: '每个（股票代码 + 条件类型）组合只支持一条预警 — 例如同一股票可同时设置「价格 ≥」和「价格 ≤」，但不能设置两条「价格 ≥」预警。',
    },
    notifications: {
      heading: '7. 通知中心',
      intro: '顶栏中的青色铃铛图标是「通知中心」 — 无需刷新页面即可实时接收各类应用内事件。',
      features: [
        { icon: '🔔', title: '预警触发',   desc: '您设置的价格或涨跌幅预警已触发。点击查看股票代码和阈值详情。' },
        { icon: '📊', title: '成交量异动', desc: '您自选股中某只股票出现相对近期历史异常放大的成交量。' },
        { icon: '📰', title: '新闻信号',   desc: 'NOVA AI 从重要新闻中提取了与您自选股相关的高置信度信号。' },
        { icon: '🔴', title: '情绪转变',   desc: '保留功能，将用于推送重要的市场情绪方向性变化。' },
      ],
      liveHeading: '实时推送',
      liveBody: '通知通过实时连接即时推送至您的浏览器。通知下拉面板标题旁的绿色小圆点表示连接处于活跃状态。若显示灰色，说明正在自动重连，无需任何操作。',
      readHeading: '标记已读',
      readBody: '点击任意通知上的对勾图标将其标记为已读，或使用下拉面板顶部的「全部标记已读」按钮批量处理。未读通知数量显示在徽章上。通知跨会话持久保存，即使您离线时收到的通知，重新登录后也不会错过。',
    },
    sectors: {
      heading: '8. 板块分析',
      intro: '「板块」页面（需登录）提供市场结构的宏观视图，从顶部导航栏进入。',
      gicsHeading: 'GICS 板块',
      gicsBody: '所有股票均按全球行业分类标准（GICS）进行分类。每个板块卡片显示该板块的股票数量、AI 生成的情绪评分，以及市值最高的龙头股列表。点击板块可将仪表盘过滤至该板块。',
      themesHeading: 'AI 热门主题',
      themesBody: 'GICS 板块下方，FlowDesktop 展示「动态主题」 — 由 NOVA 从近期新闻和信号中识别的跨板块叙事（例如「AI 基础设施建设」、「利率敏感」、「中国复苏交易」）。每个主题包含相关股票列表和简短叙述。',
      relHeading: '股票关联关系',
      relBody: '在每个板块内，FlowDesktop 基于市场行为识别同类股票。相关股票会显示在个股详情页，便于快速找到可比标的。',
    },
    intelligence: {
      heading: '9. 市场情报',
      intro: '「情报」页面（需登录）是 FlowDesktop 的 AI 精选新闻与信号流，在每个交易日内持续更新。从顶部导航栏进入。',
      newsHeading: '新闻标签',
      newsBody: '来自全球金融新闻、交易所公告及社区的多元渠道精选头条。每条新闻显示来源、时间戳和相关性标签。',
      signalsHeading: '信号标签',
      signalsBody: 'NOVA 对每条新闻进行处理，生成结构化的市场信号，包含：',
      signalItems: [
        '信号类型 — 财报、宏观、监管、地缘政治、板块等',
        '情绪值 — −1.0（极度看空）至 +1.0（极度看多）',
        '置信度 — 模型对其判断的确信程度',
        '影响时限 — 即时 / 短期 / 中期 / 长期',
        '受影响股票 — 被识别为受到影响的具体股票代码',
      ],
      sectorHeading: '板块情报标签',
      sectorBody: '每日 AI 生成的板块叙事，将某一 GICS 板块的所有信号综合提炼为简洁的展望报告 — 包含看多/看空/中性立场、核心驱动因素和重要个股。',
      tip: '高置信度信号，若涉及您自选股中的个股，将自动推送至通知中心，以「新闻信号」通知形式呈现。',
    },
    nova: {
      heading: '10. NOVA AI 助手',
      intro: 'NOVA（网络化观测价值分析师）是 FlowDesktop 内置的 AI 财务助手。它能直接访问您的自选股、实时行情、历史价格数据和板块情报，确保每一条回答都基于真实数据，而非泛泛的通用知识。',
      openHeading: '打开聊天面板',
      openBody: '点击仪表盘或自选股页面右下角的 ✦ NOVA 悬浮按钮，聊天面板从右侧滑出，无需离开当前页面。该功能仅在仪表盘和自选股页面可用（市场数据上下文最为丰富的两个页面）。',
      modesHeading: 'AI 提供商模式',
      platformTitle: 'FlowDesktop AI（平台模式）',
      platformBody: '全托管模式，无需 API Key 或任何配置。FlowDesktop 在后台自动处理一切。消耗您套餐的 AI 消息配额。',
      byokTitle: '使用自己的 Key（BYOK）',
      byokBody: '接入您自己的 OpenAI、Anthropic、Google、DeepSeek、Qwen 或 MiniMax API Key。无限使用，费用直接结算至您的提供商账号，不消耗 FlowDesktop 配额。',
      memoryHeading: '跨会话记忆',
      memoryBody: 'NOVA 能记住您在对话中分享的信息。若您告知 NOVA 您的风险偏好、偏好的交易所、投资期限或投资组合风格，它会将这些信息保存为「记忆」，并自动个性化每次后续回复。您可在设置中查看和删除已保存的记忆。',
      briefHeading: '每日简报',
      briefBody: '每天早晨，NOVA 会根据您的自选股生成个性化市场简报 — 隔夜主要涨跌情况、宏观新闻头条和板块展望。简报显示在仪表盘顶部，打开聊天面板也可重新生成。',
    },
    novaCommands: {
      heading: '11. NOVA 命令',
      intro: '点击聊天面板内的 ⌘ 图标打开命令面板，或输入 / 搜索命令。您也可以直接用自然语言提问，NOVA 会自动判断最适合的分析模式。',
      features: [
        { icon: '📈', title: '个股分析',     desc: '对指定股票进行深度分析 — 价格走势、趋势、技术指标、基本面亮点，以及 NOVA 的最终研判。' },
        { icon: '⚖️', title: '投资委员会',   desc: '三位 AI 代理（多头、空头、风控）从对立角度辩论该股票，最终形成委员会裁决。' },
        { icon: '🔄', title: '股票对比',     desc: '两只或多只股票的横向对比 — 业绩表现、估值、动量和板块背景。' },
        { icon: '🌐', title: '宏观影响',     desc: '描述一个宏观事件（如"美联储加息 50bps"），NOVA 分析其对您自选股中各只股票的可能影响。' },
        { icon: '🧪', title: '策略构建器',   desc: '用自然语言描述进出场策略，NOVA 根据历史价格数据进行回测。' },
        { icon: '🔍', title: '股票筛选',     desc: '跨 15,000+ 股票的自然语言筛选器，如「中国科技股，市值 > 50亿美元，今日下跌 3%」。' },
        { icon: '💼', title: '模拟投资组合', desc: '纸面交易日志。记录虚拟交易，请 NOVA 分析您的投资组合表现和行为模式。' },
        { icon: '📊', title: '板块分析',     desc: '向 NOVA 询问任意 GICS 板块的展望 — 情绪、主要涨跌股和关键风险。' },
      ],
      focusHeading: '焦点股票',
      focusBody: '点击任意股票行上的 ✦ 图标，将该股票设为当前活跃焦点。针对股票的命令（分析、委员会、对比、策略）将立即执行，无需再手动输入代码。',
      toolsHeading: '实时数据获取',
      toolsBody: '当 NOVA 需要上下文中尚未包含的实时数据时，会主动查询 FlowDesktop 市场数据系统。此过程会显示短暂的「正在获取数据…」提示。最终回复始终基于最新数据。',
      tip: '无论是否已加入自选股，NOVA 都能即时获取几乎任何有效股票代码的最新数据，只需直接提问即可。',
    },
    history: {
      heading: '12. 对话历史',
      intro: '所有 NOVA 对话均保存在您的本地浏览器中，从不上传至 FlowDesktop 服务器。通过顶部导航栏的「对话历史」进入（需登录）。',
      features: [
        { icon: '🗂️', title: '浏览对话',   desc: '按最近时间排序浏览所有历史会话，每条记录显示首条消息和消息总数。' },
        { icon: '🔍', title: '搜索',       desc: '在所有对话内容中全文搜索 — 即时找到任何历史分析记录。' },
        { icon: '★',  title: '收藏',       desc: '为重要对话加星，将其置顶至收藏筛选视图。' },
        { icon: '📋', title: '复制为文本', desc: '将任意对话导出为纯文本，用于笔记或报告。' },
        { icon: '💾', title: '导出 JSON',  desc: '下载原始对话 JSON 文件，供程序化使用。' },
        { icon: '↗️', title: '在聊天中打开', desc: '在实时聊天面板中重新打开历史对话，继续之前的讨论。' },
      ],
      note: '对话历史存储在您的浏览器本地，与设备绑定。清除浏览器数据将删除所有对话历史。请使用「导出 JSON」功能备份重要会话。',
    },
    settings: {
      heading: '13. 设置',
      intro: '通过右上角用户头像菜单进入「设置」。所有更改均保存至您的账号档案。',
      displayHeading: '显示',
      displayBody: '语言 — 在英文和简体中文之间切换，更多语言即将上线。\n表格密度 — 股票列表的行间距，可选「标准」或「紧凑」。',
      dataHeading: '数据',
      dataBody: '市场指数 和 涨跌榜 — 开启或关闭仪表盘中的对应组件。\n默认交易所 / 货币 / 时区 — 个性化数据展示方式。',
      aiHeading: 'AI 助手',
      aiBody1: '在「FlowDesktop AI」（托管模式，消耗配额）和「使用自己的 Key」（BYOK，无限制）之间切换。BYOK 模式下，选择提供商并粘贴您的 API Key — Key 经安全处理后仅存储在您的浏览器中，永远不会发送至 FlowDesktop 服务器。',
      aiBody2: '保存前使用「验证」按钮确认 Key 有效。配额栏显示您的剩余免费试用消息数。',
      accountHeading: '账号',
      accountBody: '更新您的显示名称、邮箱、头像（JPG 或 PNG，最大 16 KB）和个人简介。更改将同步至您的账号档案。',
    },
    pricing: {
      heading: '14. 套餐与定价',
      intro: '所有市场数据功能（行情、K 线图、自选股、板块、情报）对所有用户免费开放。仅 NOVA AI 回复功能按套餐区分。',
      plans: [
        { plan: '免费试用',   detail: '10 条 AI 消息或 7 天，以先到期者为准。无需信用卡。' },
        { plan: 'BYOK',      detail: '使用自己的 API Key，AI 无限制使用。完整市场数据，不包含 FlowDesktop AI。' },
        { plan: '基础版',    detail: '每月 200 条 AI 消息。完整市场数据、个股分析与对比。' },
        { plan: '专业版',    detail: '每月 1,000 条 AI 消息。基础版全部功能 + 高级分析和优先支持。' },
        { plan: '无限版',    detail: 'AI 消息无限制。专业版全部功能 + 专属支持。' },
      ],
      body: '前往「套餐与定价」页面对比套餐并升级。支付由 Stripe 安全处理，付款成功后账号自动升级，无需任何手动操作。',
      tip: '有关团队或企业套餐咨询？请通过定价页面底部的反馈链接与我们联系。',
    },
  },
  cta: {
    heading: '准备好开始了吗？',
    body: '从仪表盘出发，将几只股票加入自选股，然后打开 NOVA 让它分析您的投资组合。',
    dashboard: '前往仪表盘',
    pricing:   '查看套餐',
  },
}

// ── Shared UI components ─────────────────────────────────────────────────────

function SectionHeading({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="text-xs font-bold tracking-widest uppercase text-[var(--fd-text-secondary)] border-l-2 border-[var(--color-accent)] pl-3 mb-4 scroll-mt-20">
      {children}
    </h2>
  )
}
function SubHeading({ children }: { children: React.ReactNode }) {
  return <h3 className="text-sm font-semibold text-[var(--color-accent)] mb-2 mt-5">{children}</h3>
}
function Tip({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-2.5 bg-[var(--fd-bg-elev)] border-l-2 border-[var(--color-accent)] px-4 py-3 text-[12px] text-[#8aacca] leading-relaxed my-3">
      <span className="shrink-0 font-bold text-[var(--color-accent)]">TIP</span>
      <span>{children}</span>
    </div>
  )
}
function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-2.5 bg-[#1a1000] border-l-2 border-amber-500/60 px-4 py-3 text-[12px] text-[#c8a860] leading-relaxed my-3">
      <span className="shrink-0 font-bold text-amber-400">NOTE</span>
      <span>{children}</span>
    </div>
  )
}
function FeatureGrid({ items }: { items: FeatureItem[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-[var(--fd-rule)] my-4">
      {items.map((item) => (
        <div key={item.title} className="bg-[var(--fd-bg)] px-4 py-3 flex gap-3 items-start">
          <span className="text-lg shrink-0 mt-0.5">{item.icon}</span>
          <div>
            <p className="text-[12px] font-semibold text-[#c8d8ea]">{item.title}</p>
            <p className="text-[11px] text-[#5a8aaa] leading-snug mt-0.5">{item.desc}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Guide() {
  const { i18n } = useTranslation()
  const c = i18n.language.startsWith('zh') ? ZH : EN
  const s = c.sections

  return (
    <div className="max-w-3xl mx-auto py-8 space-y-12">

      {/* Hero */}
      <div>
        <p className="text-[var(--color-accent)] text-xs font-bold tracking-widest uppercase mb-2">{c.meta.badge}</p>
        <h1 className="text-3xl font-bold text-[var(--fd-text-primary)] tracking-tight mb-3">{c.meta.title}</h1>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{c.meta.intro}</p>
      </div>

      {/* Table of contents */}
      <div className="bg-[#080f18] border border-[var(--fd-rule)] px-5 py-4">
        <p className="text-[11px] font-bold tracking-widest uppercase text-[#5a8aaa] mb-3">
          {i18n.language.startsWith('zh') ? '目录' : 'Contents'}
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
          {c.toc.map((item) => (
            <a key={item.id} href={`#${item.id}`} className="text-[12px] text-[#7ab0d8] hover:text-[var(--color-nova)] transition-colors">
              {item.label}
            </a>
          ))}
        </div>
      </div>

      {/* 1. Getting Started */}
      <section id="getting-started">
        <SectionHeading id="getting-started">{s.gettingStarted.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{s.gettingStarted.intro}</p>
        <SubHeading>{s.gettingStarted.accountHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.gettingStarted.accountBody}</p>
        <SubHeading>{s.gettingStarted.trialHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.gettingStarted.trialBody}</p>
        <Tip>{s.gettingStarted.tip}</Tip>
      </section>

      {/* 2. Dashboard */}
      <section id="dashboard">
        <SectionHeading id="dashboard">{s.dashboard.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{s.dashboard.intro}</p>
        <FeatureGrid items={s.dashboard.features} />
        <SubHeading>{s.dashboard.filtersHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.dashboard.filtersBody}</p>
        <SubHeading>{s.dashboard.viewHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.dashboard.viewBody}</p>
        <Tip>{s.dashboard.tip}</Tip>
      </section>

      {/* 3. Search */}
      <section id="search">
        <SectionHeading id="search">{s.search.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.search.body}</p>
        <Note>{s.search.note}</Note>
      </section>

      {/* 4. Stock Detail */}
      <section id="stock-detail">
        <SectionHeading id="stock-detail">{s.stockDetail.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{s.stockDetail.intro}</p>
        <FeatureGrid items={s.stockDetail.features} />
        <SubHeading>{s.stockDetail.chartHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.stockDetail.chartBody}</p>
      </section>

      {/* 5. Watchlist */}
      <section id="watchlist">
        <SectionHeading id="watchlist">{s.watchlist.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{s.watchlist.intro}</p>
        <SubHeading>{s.watchlist.addHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.watchlist.addBody}</p>
        <SubHeading>{s.watchlist.removeHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.watchlist.removeBody}</p>
        <SubHeading>{s.watchlist.alertsTabHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.watchlist.alertsTabBody}</p>
        <Tip>{s.watchlist.tip}</Tip>
      </section>

      {/* 6. Alerts */}
      <section id="alerts">
        <SectionHeading id="alerts">{s.alerts.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{s.alerts.intro}</p>
        <SubHeading>{s.alerts.createHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.alerts.createBody}</p>
        <ul className="list-disc list-inside text-[12px] text-[#8aacca] space-y-1 mt-2 ml-2">
          {s.alerts.types.map((t) => <li key={t}>{t}</li>)}
        </ul>
        <SubHeading>{s.alerts.bellHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.alerts.bellBody}</p>
        <Note>{s.alerts.note}</Note>
      </section>

      {/* 7. Notifications */}
      <section id="notifications">
        <SectionHeading id="notifications">{s.notifications.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{s.notifications.intro}</p>
        <FeatureGrid items={s.notifications.features} />
        <SubHeading>{s.notifications.liveHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.notifications.liveBody}</p>
        <SubHeading>{s.notifications.readHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.notifications.readBody}</p>
      </section>

      {/* 8. Sectors */}
      <section id="sectors">
        <SectionHeading id="sectors">{s.sectors.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{s.sectors.intro}</p>
        <SubHeading>{s.sectors.gicsHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.sectors.gicsBody}</p>
        <SubHeading>{s.sectors.themesHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.sectors.themesBody}</p>
        <SubHeading>{s.sectors.relHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.sectors.relBody}</p>
      </section>

      {/* 9. Intelligence */}
      <section id="intelligence">
        <SectionHeading id="intelligence">{s.intelligence.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{s.intelligence.intro}</p>
        <SubHeading>{s.intelligence.newsHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.intelligence.newsBody}</p>
        <SubHeading>{s.intelligence.signalsHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.intelligence.signalsBody}</p>
        <ul className="list-disc list-inside text-[12px] text-[#8aacca] space-y-1 mt-2 ml-2">
          {s.intelligence.signalItems.map((item) => <li key={item}>{item}</li>)}
        </ul>
        <SubHeading>{s.intelligence.sectorHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.intelligence.sectorBody}</p>
        <Tip>{s.intelligence.tip}</Tip>
      </section>

      {/* 10. NOVA */}
      <section id="nova">
        <SectionHeading id="nova">{s.nova.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{s.nova.intro}</p>
        <SubHeading>{s.nova.openHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.nova.openBody}</p>
        <SubHeading>{s.nova.modesHeading}</SubHeading>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-[var(--fd-rule)] my-4">
          <div className="bg-[var(--fd-bg)] px-4 py-3">
            <p className="text-[12px] font-semibold text-[#c8d8ea] mb-1">{s.nova.platformTitle}</p>
            <p className="text-[11px] text-[#5a8aaa] leading-snug">{s.nova.platformBody}</p>
          </div>
          <div className="bg-[var(--fd-bg)] px-4 py-3">
            <p className="text-[12px] font-semibold text-[#c8d8ea] mb-1">{s.nova.byokTitle}</p>
            <p className="text-[11px] text-[#5a8aaa] leading-snug">{s.nova.byokBody}</p>
          </div>
        </div>
        <SubHeading>{s.nova.memoryHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.nova.memoryBody}</p>
        <SubHeading>{s.nova.briefHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.nova.briefBody}</p>
      </section>

      {/* 11. NOVA Commands */}
      <section id="nova-commands">
        <SectionHeading id="nova-commands">{s.novaCommands.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{s.novaCommands.intro}</p>
        <FeatureGrid items={s.novaCommands.features} />
        <SubHeading>{s.novaCommands.focusHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.novaCommands.focusBody}</p>
        <SubHeading>{s.novaCommands.toolsHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.novaCommands.toolsBody}</p>
        <Tip>{s.novaCommands.tip}</Tip>
      </section>

      {/* 12. History */}
      <section id="history">
        <SectionHeading id="history">{s.history.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{s.history.intro}</p>
        <FeatureGrid items={s.history.features} />
        <Note>{s.history.note}</Note>
      </section>

      {/* 13. Settings */}
      <section id="settings">
        <SectionHeading id="settings">{s.settings.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-3">{s.settings.intro}</p>
        <SubHeading>{s.settings.displayHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed whitespace-pre-line">{s.settings.displayBody}</p>
        <SubHeading>{s.settings.dataHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed whitespace-pre-line">{s.settings.dataBody}</p>
        <SubHeading>{s.settings.aiHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.settings.aiBody1}</p>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mt-2">{s.settings.aiBody2}</p>
        <SubHeading>{s.settings.accountHeading}</SubHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed">{s.settings.accountBody}</p>
      </section>

      {/* 14. Pricing */}
      <section id="pricing">
        <SectionHeading id="pricing">{s.pricing.heading}</SectionHeading>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mb-4">{s.pricing.intro}</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-[var(--fd-rule)]">
          {s.pricing.plans.map(({ plan, detail }) => (
            <div key={plan} className="bg-[var(--fd-bg)] px-4 py-3">
              <p className="text-[12px] font-semibold text-[#c8d8ea]">{plan}</p>
              <p className="text-[11px] text-[#5a8aaa] leading-snug mt-0.5">{detail}</p>
            </div>
          ))}
        </div>
        <p className="text-[var(--fd-text-dim)] text-sm leading-relaxed mt-4">{s.pricing.body}{' '}
          <Link to="/pricing" className="text-[#7ab0d8] hover:text-[var(--color-nova)]">
            {i18n.language.startsWith('zh') ? '套餐与定价' : 'Pricing page'}
          </Link>.
        </p>
        <Tip>{s.pricing.tip}</Tip>
      </section>

      {/* CTA */}
      <div className="bg-[#080f18] border border-[var(--fd-rule)] px-5 py-6 text-center space-y-3">
        <p className="text-[#c8d8ea] text-sm font-semibold">{c.cta.heading}</p>
        <p className="text-[#6a8aa8] text-[12px]">{c.cta.body}</p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center pt-1">
          <Link to="/" className="px-5 py-2 bg-[var(--color-accent)] hover:bg-[#106ebe] text-white text-sm font-semibold transition-colors">
            {c.cta.dashboard}
          </Link>
          <Link to="/pricing" className="px-5 py-2 border border-[var(--color-accent)]/50 hover:border-[var(--color-accent)] text-[var(--color-accent)] text-sm font-semibold transition-colors">
            {c.cta.pricing}
          </Link>
        </div>
      </div>

    </div>
  )
}
