import { useEffect, useLayoutEffect, useRef, useState, startTransition, type ReactNode, type ChangeEvent, type MouseEvent as ReactMouseEvent, type TouchEvent as ReactTouchEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { api, UserAccount, UserProfile, type ChatQuotaInfo } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { type LLMProviderName } from '../contexts/LLMContext'
import { useLLMContext } from '../contexts/useLLMContext'
import { LLM_PROVIDERS } from '../contexts/llmProviders'
import { PAID_PLANS } from '../config/plans'
import Modal from '../components/Modal'
import PushToggle from '../components/PushToggle'
import NotificationPrefsPanel from '../components/NotificationPrefsPanel'
import PlanUsagePanel from '../components/PlanUsagePanel'
import InvestorProfilePanel from '../components/InvestorProfilePanel'
import { ARCHETYPES, PORTRAITS, resolveAvatarValue } from '../utils/avatars'
import { useAvatar } from '../contexts/useAvatarContext'

// ── Avatar constants ──────────────────────────────────────────────────────────
const CROP_SIZE = 256
const OUTPUT_SIZE = 128
const MAX_BYTES = 16_384

// ── Shared sub-components ─────────────────────────────────────────────────────

interface SettingItemProps {
  label: string
  description?: string
  children: ReactNode
}

function SettingItem({ label, description, children }: SettingItemProps) {
  return (
    <div className="flex items-start sm:items-center justify-between gap-6 py-4 border-b border-border last:border-0 flex-col sm:flex-row">
      <div className="shrink-0 sm:w-48">
        <p className="text-sm font-semibold text-[var(--fd-text-primary)]">{label}</p>
        {description && <p className="text-xs text-[var(--fd-text-dim)] mt-0.5">{description}</p>}
      </div>
      <div className="flex-1 w-full min-w-0">
        {children}
      </div>
    </div>
  )
}

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="relative bg-surface-card border border-border pt-7 px-5 pb-1 mt-4">
      {/* Title badge centered on top border — border passes through middle */}
      <div className="absolute -top-3.5 left-4">
        <span className="bg-[var(--color-accent)] text-white text-xs font-bold tracking-widest uppercase px-4 py-1.5 inline-block">
          {title}
        </span>
      </div>
      {children}
    </div>
  )
}

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

function SaveButton({ state, onClick }: { state: SaveState; onClick: () => void }) {
  const { t } = useTranslation()
  const label = state === 'saving' ? t('settings.saving')
    : state === 'saved' ? t('settings.saved')
    : state === 'error' ? t('settings.saveError')
    : t('settings.save')

  return (
    <button
      onClick={onClick}
      disabled={state === 'saving'}
      className={`px-4 py-1.5 text-sm font-semibold transition-colors ${
        state === 'saved'
          ? 'bg-[#107c10] text-white'
          : state === 'error'
          ? 'bg-[#d13438] text-white'
          : 'bg-[var(--color-accent)] text-white hover:bg-[#106ebe]'
      } disabled:opacity-50`}
    >
      {label}
    </button>
  )
}

// ── Avatar Editor ─────────────────────────────────────────────────────────────

interface AvatarEditorProps {
  currentValue: string
  onChange: (value: string) => void
  onUiStateChange?: (state: 'idle' | 'cropping' | 'uploading') => void
  disabled?: boolean
}

function AvatarEditor({ currentValue, onChange, onUiStateChange, disabled = false }: AvatarEditorProps) {
  const { i18n } = useTranslation()
  const fileRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState(currentValue)
  const [uiState, setUiState] = useState<'idle' | 'cropping' | 'uploading'>('idle')
  const [showPicker, setShowPicker] = useState(false)
  const { ssoPicture } = useAvatar()

  const updateUiState = (s: 'idle' | 'cropping' | 'uploading') => {
    setUiState(s)
    onUiStateChange?.(s)
  }

  // Cropper state
  const [cropObjectUrl, setCropObjectUrl] = useState('')
  const [scale, setScale] = useState(1)
  const [minScale, setMinScale] = useState(1)
  const [imgLeft, setImgLeft] = useState(0)
  const [imgTop, setImgTop] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number } | null>(null)

  const sourceImgRef = useRef<HTMLImageElement | null>(null)
  const dragRef = useRef<{ startX: number; startY: number; startLeft: number; startTop: number } | null>(null)
  const liveRef = useRef({ scale: 1, imgLeft: 0, imgTop: 0 })
  useLayoutEffect(() => { liveRef.current = { scale, imgLeft, imgTop } }, [scale, imgLeft, imgTop])

  useEffect(() => { setPreview(currentValue) }, [currentValue])

  const isZh = i18n.language === 'zh' || i18n.language.startsWith('zh-')
  const strings = {
    uploadPhoto: isZh ? '上传头像' : 'Upload photo',
    changePhoto: isZh ? '更换头像' : 'Change photo',
    remove:      isZh ? '移除' : 'Remove',
    apply:       isZh ? '确认' : 'Apply',
    cancel:      isZh ? '取消' : 'Cancel',
    cropHint:    isZh ? '拖动调整位置 · 滚轮缩放' : 'Drag to reposition · scroll to zoom',
    hint:        isZh ? '支持 JPG · PNG · GIF · 最大 16 KB' : 'JPG · PNG · GIF · max 16 KB',
    pick:        isZh ? 'FlowDesktop 头像' : 'FlowDesktop avatars',
    useSignin:   isZh ? '使用登录头像' : 'Use sign-in photo',
    archetypes:  isZh ? '风格化形象' : 'Archetypes',
    portraits:   isZh ? '人物肖像' : 'Portraits',
  }

  const selectNative = (key: string) => {
    const v = `fd:${key}`
    setPreview(v)
    onChange(v)
    setShowPicker(false)
  }

  function clamp(left: number, top: number, sc: number): [number, number] {
    const img = sourceImgRef.current
    if (!img) return [left, top]
    return [
      Math.min(0, Math.max(CROP_SIZE - img.naturalWidth * sc, left)),
      Math.min(0, Math.max(CROP_SIZE - img.naturalHeight * sc, top)),
    ]
  }

  function applyZoom(newScale: number) {
    const img = sourceImgRef.current
    if (!img) return
    const { scale: sc, imgLeft: l, imgTop: tp } = liveRef.current
    const cx = CROP_SIZE / 2
    const relX = (cx - l) / (img.naturalWidth * sc)
    const relY = (cx - tp) / (img.naturalHeight * sc)
    const [nl, nt] = clamp(
      cx - relX * img.naturalWidth * newScale,
      cx - relY * img.naturalHeight * newScale,
      newScale,
    )
    liveRef.current = { scale: newScale, imgLeft: nl, imgTop: nt }
    setScale(newScale)
    setImgLeft(nl)
    setImgTop(nt)
  }

  useEffect(() => {
    if (!isDragging) return
    const onMove = (e: MouseEvent | TouchEvent) => {
      e.preventDefault()
      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY
      if (!dragRef.current) return
      const { scale: sc } = liveRef.current
      const [nl, nt] = clamp(
        dragRef.current.startLeft + clientX - dragRef.current.startX,
        dragRef.current.startTop + clientY - dragRef.current.startY,
        sc,
      )
      setImgLeft(nl)
      setImgTop(nt)
    }
    const onUp = () => { setIsDragging(false); dragRef.current = null }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('touchmove', onMove, { passive: false })
    window.addEventListener('mouseup', onUp)
    window.addEventListener('touchend', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('touchmove', onMove)
      window.removeEventListener('mouseup', onUp)
      window.removeEventListener('touchend', onUp)
    }
  }, [isDragging])

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (fileRef.current) fileRef.current.value = ''
    const objUrl = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      const ms = Math.max(CROP_SIZE / img.naturalWidth, CROP_SIZE / img.naturalHeight)
      sourceImgRef.current = img
      setNaturalSize({ width: img.naturalWidth, height: img.naturalHeight })
      setCropObjectUrl(objUrl)
      setMinScale(ms)
      setScale(ms)
      setImgLeft((CROP_SIZE - img.naturalWidth * ms) / 2)
      setImgTop((CROP_SIZE - img.naturalHeight * ms) / 2)
      updateUiState('cropping')
    }
    img.onerror = () => URL.revokeObjectURL(objUrl)
    img.src = objUrl
  }

  const cleanupCrop = () => {
    if (cropObjectUrl) URL.revokeObjectURL(cropObjectUrl)
    setCropObjectUrl('')
    sourceImgRef.current = null
    setNaturalSize(null)
  }

  const handleApply = async () => {
    const img = sourceImgRef.current
    if (!img) return
    updateUiState('uploading')

    const canvas = document.createElement('canvas')
    canvas.width = OUTPUT_SIZE
    canvas.height = OUTPUT_SIZE
    const ctx = canvas.getContext('2d')!
    const { scale: sc, imgLeft: l, imgTop: tp } = liveRef.current
    ctx.drawImage(img, -l / sc, -tp / sc, CROP_SIZE / sc, CROP_SIZE / sc, 0, 0, OUTPUT_SIZE, OUTPUT_SIZE)

    let quality = 0.85
    let dataUrl = canvas.toDataURL('image/jpeg', quality)
    while (dataUrl.length * 0.75 > MAX_BYTES && quality > 0.1) {
      quality -= 0.05
      dataUrl = canvas.toDataURL('image/jpeg', quality)
    }

    // For FlowDesktop we store the data URL directly as the avatar value
    // (the Keycloak account API will persist it as a user attribute)
    cleanupCrop()
    setPreview(dataUrl)
    onChange(dataUrl)
    updateUiState('idle')
  }

  const handleCancel = () => { cleanupCrop(); updateUiState('idle') }
  const handleRemove = () => { setPreview(''); onChange('') }

  const onDragStart = (e: ReactMouseEvent | ReactTouchEvent) => {
    e.preventDefault()
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY
    dragRef.current = { startX: clientX, startY: clientY, startLeft: imgLeft, startTop: imgTop }
    setIsDragging(true)
  }

  const overrideUrl = resolveAvatarValue(preview)
  const displayUrl = overrideUrl || ssoPicture || ''  // what the circle shows (effective)
  const hasOverride = !!overrideUrl                    // user set an explicit avatar
  const hasImage = !!displayUrl

  // ── Cropping UI ──
  if (uiState === 'cropping' || uiState === 'uploading') {
    return (
      <div className="flex flex-col gap-3" style={{ maxWidth: CROP_SIZE }}>
        <p className="text-xs text-[#666]">{strings.cropHint}</p>
        <div
          className="avatar-circle relative select-none"
          style={{
            width: CROP_SIZE, height: CROP_SIZE, borderRadius: '50%',
            overflow: 'hidden', border: '2px solid var(--color-nova)', background: '#000',
            cursor: uiState === 'uploading' ? 'default' : isDragging ? 'grabbing' : 'grab',
          }}
          onMouseDown={uiState !== 'uploading' ? onDragStart : undefined}
          onTouchStart={uiState !== 'uploading' ? onDragStart : undefined}
          onWheel={(e) => {
            if (uiState === 'uploading') return
            e.preventDefault()
            const step = minScale * 0.08
            applyZoom(Math.min(Math.max(liveRef.current.scale + (e.deltaY < 0 ? step : -step), minScale), minScale * 4))
          }}
        >
          {cropObjectUrl && (
            <img
              src={cropObjectUrl}
              draggable={false}
              style={{
                position: 'absolute', left: imgLeft, top: imgTop, pointerEvents: 'none',
                width: naturalSize ? naturalSize.width * scale : 'auto',
                height: naturalSize ? naturalSize.height * scale : 'auto',
              }}
            />
          )}
        </div>
        {uiState !== 'uploading' && (
          <>
            <div className="flex items-center gap-2">
              <button type="button" className="w-7 h-7 flex items-center justify-center border border-border bg-[var(--fd-bg-elevated)] text-[var(--fd-text-dim)] text-base" onClick={() => applyZoom(Math.max(liveRef.current.scale - minScale * 0.1, minScale))}>−</button>
              <input type="range" min={0} max={100} step={1} className="flex-1" style={{ accentColor: 'var(--color-nova)' }} value={Math.round((scale - minScale) / (minScale * 3) * 100)} onChange={(e) => applyZoom(minScale + parseInt(e.target.value) / 100 * minScale * 3)} />
              <button type="button" className="w-7 h-7 flex items-center justify-center border border-border bg-[var(--fd-bg-elevated)] text-[var(--fd-text-dim)] text-base" onClick={() => applyZoom(Math.min(liveRef.current.scale + minScale * 0.1, minScale * 4))}>+</button>
            </div>
            <div className="flex gap-2">
              <button type="button" className="px-4 py-1 text-sm font-semibold bg-[var(--color-accent)] text-white" onClick={handleApply}>{strings.apply}</button>
              <button type="button" className="px-4 py-1 text-sm text-[var(--fd-text-dim)] hover:text-[var(--fd-text-secondary)]" onClick={handleCancel}>{strings.cancel}</button>
            </div>
          </>
        )}
      </div>
    )
  }

  // ── Idle UI ──
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-5">
        {/* Circular avatar preview */}
        <div
          className="avatar-circle shrink-0 flex items-center justify-center overflow-hidden"
          style={{
            width: 80, height: 80, borderRadius: '50%',
            border: `2px solid ${hasImage ? 'var(--color-nova)' : 'var(--fd-rule)'}`,
            background: 'var(--fd-bg-elevated)', transition: 'border-color 0.2s',
          }}
        >
          {hasImage ? (
            <img src={displayUrl} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={() => setPreview('')} />
          ) : (
            <svg viewBox="0 0 40 40" width={40} height={40} fill="var(--fd-text-faint)">
              <circle cx="20" cy="14" r="8" />
              <ellipse cx="20" cy="36" rx="14" ry="10" />
            </svg>
          )}
        </div>
        {/* Buttons */}
        <div className="flex flex-col gap-2">
          <button
            type="button"
            disabled={disabled}
            onClick={() => fileRef.current?.click()}
            className="px-4 py-1.5 text-xs font-medium border border-border bg-[var(--fd-bg-elevated)] text-[var(--color-nova)] hover:border-[var(--color-nova)] transition-colors disabled:opacity-50"
          >
            {hasOverride ? strings.changePhoto : strings.uploadPhoto}
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => setShowPicker((v) => !v)}
            className="px-4 py-1.5 text-xs font-medium border border-border bg-[var(--fd-bg-elevated)] text-[var(--fd-text-dim)] hover:border-[var(--color-nova)] hover:text-[var(--color-nova)] transition-colors disabled:opacity-50"
          >
            {strings.pick}
          </button>
          {ssoPicture && hasOverride && (
            <button
              type="button"
              disabled={disabled}
              onClick={() => { setPreview(''); onChange('') }}
              className="px-4 py-1.5 text-xs font-medium text-[var(--fd-text-dim)] hover:text-[var(--fd-text-secondary)] transition-colors disabled:opacity-50"
            >
              {strings.useSignin}
            </button>
          )}
          {hasOverride && (
            <button
              type="button"
              disabled={disabled}
              onClick={handleRemove}
              className="px-4 py-1.5 text-xs font-medium text-[var(--fd-text-dim)] hover:text-[var(--fd-text-secondary)] transition-colors disabled:opacity-50"
            >
              {strings.remove}
            </button>
          )}
        </div>
      </div>

      {/* FlowDesktop native avatar picker */}
      {showPicker && (
        <div className="mt-3 border border-border bg-[var(--fd-bg-elevated)] p-3 flex flex-col gap-3" style={{ borderRadius: 4 }}>
          <NativePickerGroup label={strings.archetypes} items={ARCHETYPES} selected={preview} onPick={selectNative} />
          <NativePickerGroup label={strings.portraits} items={PORTRAITS} selected={preview} onPick={selectNative} />
        </div>
      )}

      <p className="text-xs text-[var(--fd-text-faint)] mt-1">{strings.hint}</p>
      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
    </div>
  )
}

function NativePickerGroup({
  label, items, selected, onPick,
}: {
  label: string
  items: { key: string; url: string; label: string }[]
  selected: string
  onPick: (key: string) => void
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-[var(--fd-text-faint)] font-semibold mb-1.5">{label}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(48px, 1fr))', gap: 8 }}>
        {items.map((a) => {
          const isSel = selected === `fd:${a.key}`
          return (
            <button key={a.key} type="button" title={a.label} onClick={() => onPick(a.key)}
              style={{
                padding: 0, borderRadius: '50%', cursor: 'pointer', lineHeight: 0,
                border: `2px solid ${isSel ? 'var(--color-nova)' : 'transparent'}`,
                background: 'var(--fd-bg-panel)',
              }}>
              <img src={a.url} alt={a.label} width={44} height={44}
                style={{ width: 44, height: 44, borderRadius: '50%', objectFit: 'cover', display: 'block' }} />
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Style constants ───────────────────────────────────────────────────────────

const INPUT_CLS = 'w-full bg-[var(--fd-bg-elevated)] border border-border px-3 py-1.5 text-[var(--fd-text-primary)] text-sm focus:outline-none focus:bg-[var(--fd-bg-input-focus)] transition-colors'
const SELECT_CLS = 'w-full settings-select bg-[var(--fd-bg-elevated)] border border-border px-3 py-1.5 text-[var(--fd-text-secondary)] text-sm focus:outline-none focus:bg-[var(--fd-bg-input-focus)] transition-colors cursor-pointer'

const EXCHANGES = ['', 'NYSE', 'NASDAQ', 'TSX', 'SSE', 'SZSE']
const CURRENCIES = ['', 'USD', 'CAD', 'CNY']
const TIMEZONES = [
  '',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Toronto',
  'America/Vancouver',
  'Asia/Shanghai',
  'Asia/Hong_Kong',
  'Asia/Tokyo',
  'Europe/London',
  'Europe/Berlin',
  'UTC',
]

// ── BYOK Checkbox component ───────────────────────────────────────────────────

function ByokCheckbox({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <label className="flex items-center cursor-pointer shrink-0" onClick={(e) => e.stopPropagation()}>
      <input type="checkbox" checked={checked} onChange={onChange} className="sr-only" />
      <span
        className={`w-3.5 h-3.5 border flex items-center justify-center transition-colors ${
          checked ? 'border-[var(--color-accent)] bg-[var(--color-accent)]' : 'border-[var(--fd-text-faint)] bg-transparent hover:border-[var(--fd-text-dim)]'
        }`}
      >
        {checked && (
          <svg width="9" height="9" viewBox="0 0 10 10" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="square">
            <polyline points="1,5 3.5,8 9,2" />
          </svg>
        )}
      </span>
    </label>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Settings() {
  const { t } = useTranslation()
  const { isAuthenticated, username, displayName, avatar, roles } = useAuth()
  const { setValue: setAvatarValue } = useAvatar()
  const {
    mode: llmMode,
    setMode: setLLMMode,
    byokActiveProvider,
    setByokActive,
    saveKeyForProvider,
    getApiKeyForProvider,
    providers,
    selectedModel,
    setSelectedModel,
  } = useLLMContext()
  const [showApiKey, setShowApiKey] = useState(false)
  const [selectedProviderForSettings, setSelectedProviderForSettings] = useState<LLMProviderName | null>(null)
  const [keyInputValue, setKeyInputValue] = useState('')
  const [quota, setQuota] = useState<ChatQuotaInfo | null>(null)
  const [keyValidation, setKeyValidation] = useState<'idle' | 'validating' | 'valid' | 'invalid' | 'unverifiable'>('idle')

  const isByokPlan = roles.includes('fd-tier-byok')

  // Fetch quota for FlowDesktop AI tab status display
  useEffect(() => {
    if (isAuthenticated) {
      api.getChatQuota().then(setQuota).catch(() => {})
    }
  }, [isAuthenticated])

  // Auto-switch to BYOK tab for BYOK-plan users
  useEffect(() => {
    if (isByokPlan) setLLMMode('byok')
  }, [isByokPlan]) // eslint-disable-line react-hooks/exhaustive-deps

  // When BYOK tab is active and no provider is selected in the panel, auto-select the active one
  useEffect(() => {
    if (llmMode === 'byok' && byokActiveProvider && !selectedProviderForSettings) {
      setSelectedProviderForSettings(byokActiveProvider)
    }
  }, [llmMode, byokActiveProvider, selectedProviderForSettings])

  // Sync key input with selected provider; reset validation state
  useEffect(() => {
    startTransition(() => {
      setKeyInputValue(selectedProviderForSettings ? getApiKeyForProvider(selectedProviderForSettings) : '')
      setShowApiKey(false)
      setKeyValidation('idle')
    })
  }, [selectedProviderForSettings, getApiKeyForProvider])

  // Reset validation state whenever the key input changes
  useEffect(() => {
    startTransition(() => { setKeyValidation('idle') })
  }, [keyInputValue])

  // True when byokActiveProvider is set but has no key stored
  const activeProviderMissingKey = (() => {
    if (!byokActiveProvider) return false
    const key = byokActiveProvider === selectedProviderForSettings
      ? keyInputValue
      : getApiKeyForProvider(byokActiveProvider)
    return key.trim() === ''
  })()

  const handleValidateKey = async () => {
    if (!selectedProviderForSettings || !keyInputValue.trim()) return
    setKeyValidation('validating')
    try {
      const result = await api.validateApiKey(selectedProviderForSettings, keyInputValue.trim())
      if (result.valid === true) {
        setKeyValidation('valid')
      } else if (result.valid === false) {
        setKeyValidation('invalid')
      } else {
        // null = inconclusive (connection error, provider unreachable)
        setKeyValidation('unverifiable')
      }
    } catch {
      // Network error reaching our own backend
      setKeyValidation('unverifiable')
    }
  }

  // Build initial account draft from JWT token claims (available immediately)
  const initialAccount: Partial<UserAccount> = {
    username: username ?? '',
    email: '',
    firstName: '',
    lastName: '',
    avatar: avatar ?? '',
  }
  if (displayName && displayName !== username) {
    const parts = displayName.split(' ')
    initialAccount.firstName = parts[0] ?? ''
    initialAccount.lastName = parts.slice(1).join(' ')
  }

  // Account state (Keycloak)
  const [account, setAccount] = useState<UserAccount | null>(null)
  const [accountDraft, setAccountDraft] = useState<Partial<UserAccount>>(initialAccount)
  const [accountSave, setAccountSave] = useState<SaveState>('idle')
  const avatarEditorStateRef = useRef<'idle' | 'cropping' | 'uploading'>('idle')
  const [showAvatarWarning, setShowAvatarWarning] = useState(false)

  // Profile state (FlowDesktop DB)
  const [, setProfile] = useState<UserProfile | null>(null)
  const [profileDraft, setProfileDraft] = useState<Partial<UserProfile>>({})
  const [profileSave, setProfileSave] = useState<SaveState>('idle')

  // Load data from API (overrides JWT-seeded defaults with authoritative data)
  useEffect(() => {
    if (!isAuthenticated) return
    api.getAccount().then((data) => {
      setAccount(data)
      setAccountDraft(data)
    }).catch(() => {})
    api.getProfile().then((data) => {
      setProfile(data)
      setProfileDraft(data)
    }).catch(() => {})
  }, [isAuthenticated])

  const handleAccountSave = async () => {
    if (avatarEditorStateRef.current === 'cropping') {
      setShowAvatarWarning(true)
      return
    }
    setAccountSave('saving')
    try {
      const updated = await api.updateAccount({
        email: accountDraft.email,
        firstName: accountDraft.firstName,
        lastName: accountDraft.lastName,
        avatar: accountDraft.avatar,
      })
      setAccount(updated)
      setAvatarValue(updated.avatar ?? null)  // live-update header/chat avatar
      setAccountSave('saved')
    } catch {
      setAccountSave('error')
    }
    setTimeout(() => setAccountSave('idle'), 2000)
  }

  const handleProfileSave = async () => {
    setProfileSave('saving')
    try {
      const updated = await api.updateProfile({
        default_exchange: profileDraft.default_exchange || null,
        default_currency: profileDraft.default_currency || null,
        timezone: profileDraft.timezone || null,
        locale: profileDraft.locale || null,
        bio: profileDraft.bio || null,
      })
      setProfile(updated)
      setProfileSave('saved')
    } catch {
      setProfileSave('error')
    }
    setTimeout(() => setProfileSave('idle'), 2000)
  }

  return (
    <div className="space-y-8">
      {/* Page heading — title + subtitle on same row */}
      <div className="flex flex-col sm:flex-row sm:items-baseline sm:gap-3">
        <h1 className="text-2xl font-semibold text-[var(--fd-text-primary)] tracking-tight">{t('settings.title')}</h1>
        <p className="text-sm text-[var(--fd-text-dim)] mt-1 sm:mt-0">{t('settings.subtitle')}</p>
      </div>

      {/* Account (Keycloak) */}
      {isAuthenticated && (
        <SectionCard title={t('settings.sectionAccount')}>
          <SettingItem label={t('settings.username')}>
            <span className="text-sm text-[var(--fd-text-dim)]">{accountDraft.username || account?.username || '—'}</span>
          </SettingItem>
          <SettingItem label={t('settings.email')}>
            <input
              type="email"
              className={INPUT_CLS}
              value={accountDraft.email ?? ''}
              onChange={(e) => setAccountDraft({ ...accountDraft, email: e.target.value })}
            />
          </SettingItem>
          <SettingItem label={t('settings.firstName')}>
            <input
              type="text"
              className={INPUT_CLS}
              value={accountDraft.firstName ?? ''}
              onChange={(e) => setAccountDraft({ ...accountDraft, firstName: e.target.value })}
            />
          </SettingItem>
          <SettingItem label={t('settings.lastName')}>
            <input
              type="text"
              className={INPUT_CLS}
              value={accountDraft.lastName ?? ''}
              onChange={(e) => setAccountDraft({ ...accountDraft, lastName: e.target.value })}
            />
          </SettingItem>
          <SettingItem label={t('settings.avatar')} description={t('settings.avatarDesc')}>
            <AvatarEditor
              currentValue={accountDraft.avatar ?? ''}
              onChange={(value) => setAccountDraft({ ...accountDraft, avatar: value })}
              onUiStateChange={(s) => { avatarEditorStateRef.current = s }}
            />
          </SettingItem>
          <div className="flex justify-end py-3">
            <SaveButton state={accountSave} onClick={handleAccountSave} />
          </div>
        </SectionCard>
      )}

      {/* Plan & usage */}
      {isAuthenticated && (
        <SectionCard title={t('settings.sectionPlan', 'Plan & usage')}>
          <PlanUsagePanel />
        </SectionCard>
      )}

      {/* NOVA investor profile (personalization) */}
      {isAuthenticated && (
        <SectionCard title={t('settings.sectionInvestorProfile', 'Investor profile')}>
          <InvestorProfilePanel />
        </SectionCard>
      )}

      {/* Preferences (FlowDesktop DB) */}
      {isAuthenticated && (
        <SectionCard title={t('settings.sectionPreferences')}>
          <SettingItem label={t('settings.defaultExchange')} description={t('settings.defaultExchangeDesc')}>
            <select
              className={SELECT_CLS}
              value={profileDraft.default_exchange ?? ''}
              onChange={(e) => setProfileDraft({ ...profileDraft, default_exchange: e.target.value || null })}
            >
              {EXCHANGES.map((ex) => (
                <option key={ex} value={ex}>{ex || '—'}</option>
              ))}
            </select>
          </SettingItem>
          <SettingItem label={t('settings.defaultCurrency')} description={t('settings.defaultCurrencyDesc')}>
            <select
              className={SELECT_CLS}
              value={profileDraft.default_currency ?? ''}
              onChange={(e) => setProfileDraft({ ...profileDraft, default_currency: e.target.value || null })}
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>{c || '—'}</option>
              ))}
            </select>
          </SettingItem>
          <SettingItem label={t('settings.timezone')} description={t('settings.timezoneDesc')}>
            <select
              className={SELECT_CLS}
              value={profileDraft.timezone ?? ''}
              onChange={(e) => setProfileDraft({ ...profileDraft, timezone: e.target.value || null })}
            >
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>{tz || '—'}</option>
              ))}
            </select>
          </SettingItem>
          <SettingItem label={t('settings.language')} description={t('settings.languageDesc')}>
            <select
              className={SELECT_CLS}
              value={profileDraft.locale ?? ''}
              onChange={(e) => setProfileDraft({ ...profileDraft, locale: e.target.value || null })}
            >
              <option value="">—</option>
              <option value="en">English</option>
              <option value="zh">中文</option>
            </select>
          </SettingItem>
          <SettingItem label={t('settings.bio')} description={t('settings.bioDesc')}>
            <textarea
              className={`${INPUT_CLS} resize-none`}
              style={{ height: 60 }}
              placeholder={t('settings.bioPlaceholder')}
              value={profileDraft.bio ?? ''}
              onChange={(e) => setProfileDraft({ ...profileDraft, bio: e.target.value })}
            />
          </SettingItem>
          <div className="flex justify-end py-3">
            <SaveButton state={profileSave} onClick={handleProfileSave} />
          </div>
        </SectionCard>
      )}

      {/* AI Assistant */}
      {isAuthenticated && (
        <SectionCard title={t('settings.sectionAI')}>

          {/* Tab bar — FlowDesktop AI | Use My Own Key (status) */}
          <div className="flex border-b border-border">
            <button
              onClick={() => { if (!isByokPlan) setLLMMode('flowdesktop') }}
              className={`flex-1 py-2.5 text-xs font-semibold transition-colors border-b-2 ${
                llmMode === 'flowdesktop' && !isByokPlan
                  ? 'border-[var(--color-accent)] text-[var(--fd-text-primary)]'
                  : 'border-transparent text-[var(--fd-text-dim)] hover:text-[var(--fd-text-secondary)]'
              } ${isByokPlan ? 'opacity-40 cursor-not-allowed' : ''}`}
              title={isByokPlan ? t('settings.aiByokDisabledForPlan') : undefined}
            >
              {t('settings.aiModeFlowdesktop')}
            </button>
            <button
              onClick={() => setLLMMode('byok')}
              className={`flex-1 py-2.5 text-xs font-semibold transition-colors border-b-2 ${
                llmMode === 'byok'
                  ? 'border-[var(--color-accent)] text-[var(--fd-text-primary)]'
                  : 'border-transparent text-[var(--fd-text-dim)] hover:text-[var(--fd-text-secondary)]'
              }`}
            >
              {t('settings.aiModeBYOK')}
              <span className={`ml-1.5 text-[10px] font-normal ${
                activeProviderMissingKey ? 'text-[#d4a200]'
                : byokActiveProvider ? 'text-[#107c10]'
                : 'text-[var(--fd-text-dim)]'
              }`}>
                {(() => {
                  const label = LLM_PROVIDERS.find(p => p.id === byokActiveProvider)?.labelKey ?? ''
                  if (activeProviderMissingKey)
                    return `(${t(label)} — ${t('settings.aiKeyTabRequired')})`
                  if (byokActiveProvider && llmMode === 'byok')
                    return `(${t(label)} ${t('settings.aiByokTabIsActive')})`
                  if (byokActiveProvider)
                    return `(${t(label)} — ${t('settings.aiByokTabSaved')})`
                  return `(${t('settings.aiByokTabNoneActive')})`
                })()}
              </span>
            </button>
          </div>

          {/* Tab body */}
          <div className="py-4">

            {/* ── FlowDesktop AI tab ── */}
            {llmMode === 'flowdesktop' && (
              <div className="space-y-3 px-1">

                {/* BYOK plan: disabled message */}
                {isByokPlan ? (
                  <div className="flex items-start gap-3 p-3 bg-[var(--fd-bg-elevated)] border border-[var(--fd-text-faint)] text-xs text-[var(--fd-text-dim)]">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" className="shrink-0 mt-0.5 text-yellow-500">
                      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                    </svg>
                    <span>{t('settings.aiByokDisabledForPlan')}</span>
                  </div>
                ) : (
                  <>
                    {/* Quota / tier status widget */}
                    {quota && (
                      <div className="p-3 bg-[var(--fd-bg-elevated)] border border-border">
                        {quota.tier === 'admin' && (
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--color-accent)] bg-[var(--color-accent)]/10 px-2 py-0.5">
                              {t('settings.aiFlowdesktopTierAdmin')}
                            </span>
                            <span className="text-xs text-[var(--fd-text-dim)]">— Unlimited</span>
                          </div>
                        )}
                        {quota.tier === 'paid' && (() => {
                          const plan = PAID_PLANS.find(p =>
                            roles.includes(p.keycloakRole) && p.keycloakRole !== 'fd-tier-byok'
                          )
                          return (
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-[10px] font-bold uppercase tracking-widest text-[#107c10] bg-[#107c10]/10 px-2 py-0.5">
                                {plan ? t(`pricing.plan_${plan.key}`) : t('settings.aiFlowdesktopTierPaid')}
                              </span>
                              {plan && (
                                <span className="text-xs text-[var(--fd-text-dim)]">
                                  — {plan.msgLimit === '∞' ? 'Unlimited' : `${plan.msgLimit} msg / mo`}
                                </span>
                              )}
                            </div>
                          )
                        })()}
                        {quota.tier === 'free' && (
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="text-[10px] font-bold uppercase tracking-widest text-[#d4a200] bg-[#d4a200]/10 px-2 py-0.5">
                                {t('settings.aiFlowdesktopTierFree')}
                              </span>
                              {quota.trial_exhausted ? (
                                <span className="text-[10px] text-red-400">{t('settings.aiFlowdesktopTrialExhausted')}</span>
                              ) : (
                                <span className="text-[10px] text-[#666]">
                                  {t('settings.aiFlowdesktopDaysLeft', { days: quota.days_remaining ?? 0 })}
                                </span>
                              )}
                            </div>
                            {quota.limit != null && (
                              <>
                                <div className="h-1 bg-[#333] rounded-full overflow-hidden">
                                  <div
                                    className={`h-1 rounded-full transition-all ${quota.trial_exhausted ? 'bg-red-500' : 'bg-[var(--color-accent)]'}`}
                                    style={{ width: `${Math.min(100, (quota.used / quota.limit) * 100)}%` }}
                                  />
                                </div>
                                <p className="text-[10px] text-[#666]">
                                  {t('settings.aiFlowdesktopQuotaUsed', { used: quota.used, limit: quota.limit })}
                                </p>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Info table */}
                    <div className="border border-border bg-[var(--fd-bg-elevated)]">
                      <table className="w-full text-xs">
                        <tbody>
                          {[
                            ['settings.aiFlowdesktopRow1Left', 'settings.aiFlowdesktopRow1Right'],
                            ['settings.aiFlowdesktopRow2Left', 'settings.aiFlowdesktopRow2Right'],
                            ['settings.aiFlowdesktopRow3Left', 'settings.aiFlowdesktopRow3Right'],
                          ].map(([leftKey, rightKey]) => (
                            <tr key={leftKey} className="border-b border-border last:border-0">
                              <td className="px-3 py-2 text-[var(--fd-text-dim)] w-28 shrink-0">{t(leftKey)}</td>
                              <td className="px-3 py-2 text-[var(--fd-text-secondary)]">{t(rightKey)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    <p className="text-xs text-yellow-400 leading-relaxed">
                      {t('settings.aiFlowdesktopNote')}
                    </p>
                  </>
                )}
              </div>
            )}

            {/* ── Use My Own Key tab ── */}
            {llmMode === 'byok' && (
              <div className="flex gap-0" style={{ minHeight: 220, overflow: 'hidden' }}>

                {/* Left — provider list */}
                <div className="w-56 shrink-0 overflow-y-auto thin-scrollbar border-r border-border">
                  {/* No active provider hint — always visible, no layout shift */}
                  <div className="px-3 py-2 text-[10px] text-[#999] border-b border-border bg-[#111] leading-relaxed">
                    {t('settings.aiByokNoActive')}
                  </div>
                  <div className="flex flex-col">
                    {LLM_PROVIDERS.map((p) => {
                      const hasKey = !!getApiKeyForProvider(p.id)
                      const isSelected = selectedProviderForSettings === p.id
                      const isActive = byokActiveProvider === p.id

                      return (
                        <div
                          key={p.id}
                          role="button"
                          tabIndex={0}
                          onClick={() => setSelectedProviderForSettings(p.id)}
                          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedProviderForSettings(p.id) }}
                          className={`flex items-center gap-2 px-3 py-2.5 cursor-pointer transition-colors border-b border-border last:border-0 select-none ${
                            isSelected ? 'bg-[var(--color-accent)]/10' : 'hover:bg-surface-raised'
                          }`}
                        >
                          {/* Status dot: green=active+key, amber=active/configured, grey=no key */}
                          <span
                            title={
                              isActive && !hasKey
                                ? t('settings.aiKeyRequired')
                                : isActive
                                ? t('settings.aiStatusInUse')
                                : hasKey
                                ? t('settings.aiStatusActivated')
                                : t('settings.aiStatusInactive')
                            }
                            className={`w-2 h-2 shrink-0 rounded-full ${
                              isActive && !hasKey ? 'bg-[#d4a200]'
                              : isActive ? 'bg-[#107c10]'
                              : hasKey ? 'bg-[#d4a200]'
                              : 'bg-[#555]'
                            }`}
                          />

                          <span className={`flex-1 text-xs font-semibold truncate ${isSelected ? 'text-[var(--fd-text-primary)]' : 'text-[var(--fd-text-dim)]'}`}>
                            {t(p.labelKey)}
                          </span>

                          {/* Checkbox — activates provider AND selects it in the right panel */}
                          <ByokCheckbox
                            checked={isActive}
                            onChange={() => {
                              setByokActive(isActive ? null : p.id)
                              setSelectedProviderForSettings(p.id)
                            }}
                          />
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Right — settings detail for selected provider */}
                <div className="flex-1 px-4 min-w-0 py-1">
                  {selectedProviderForSettings ? (
                    <div className="space-y-3">
                      {/* Provider name + active indicator */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-[var(--fd-text-primary)]">
                          {t(LLM_PROVIDERS.find(p => p.id === selectedProviderForSettings)?.labelKey ?? '')}
                        </span>
                        {byokActiveProvider === selectedProviderForSettings && (
                          <span className="text-[10px] font-bold uppercase tracking-wider text-[#107c10] bg-[#107c10]/10 px-2 py-0.5">
                            {t('settings.aiInUse')}
                          </span>
                        )}
                      </div>

                      {/* Model selector */}
                      {(() => {
                        const currentProvider = providers.find(p => p.name === selectedProviderForSettings)
                        if (!currentProvider || currentProvider.models.length === 0) return null
                        return (
                          <select
                            className={SELECT_CLS}
                            value={selectedModel}
                            onChange={(e) => setSelectedModel(e.target.value)}
                          >
                            {currentProvider.models.map(m => (
                              <option key={m.id} value={m.id}>{m.label || m.id}</option>
                            ))}
                          </select>
                        )
                      })()}

                      {/* API key input */}
                      <div className="relative">
                        <input
                          type={showApiKey ? 'text' : 'password'}
                          className={INPUT_CLS + ' pr-20'}
                          placeholder={t('settings.aiApiKeyPlaceholder')}
                          value={keyInputValue}
                          onChange={(e) => {
                            setKeyInputValue(e.target.value)
                            saveKeyForProvider(selectedProviderForSettings, e.target.value)
                          }}
                          autoComplete="off"
                        />
                        {/* Clear button */}
                        {keyInputValue && (
                          <button
                            type="button"
                            onClick={() => {
                              setKeyInputValue('')
                              saveKeyForProvider(selectedProviderForSettings, '')
                              if (byokActiveProvider === selectedProviderForSettings) setByokActive(null)
                            }}
                            className="absolute right-9 top-1/2 -translate-y-1/2 text-[10px] text-[#666] hover:text-[#999] transition-colors uppercase tracking-wider"
                          >
                            {t('settings.aiClearKey')}
                          </button>
                        )}
                        {/* Show/hide toggle */}
                        <button
                          type="button"
                          onClick={() => setShowApiKey(!showApiKey)}
                          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--fd-text-dim)] hover:text-[var(--fd-text-secondary)] transition-colors"
                          aria-label={showApiKey ? 'Hide key' : 'Show key'}
                        >
                          {showApiKey ? (
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square" strokeLinejoin="miter">
                              <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
                              <line x1="1" y1="1" x2="23" y2="23" />
                            </svg>
                          ) : (
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square" strokeLinejoin="miter">
                              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                              <circle cx="12" cy="12" r="3" />
                            </svg>
                          )}
                        </button>
                      </div>

                      {/* Key required warning — active provider missing key */}
                      {byokActiveProvider === selectedProviderForSettings && activeProviderMissingKey && (
                        <p className="text-xs text-[#d4a200] flex items-center gap-1.5">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
                          </svg>
                          {t('settings.aiKeyRequired')}
                        </p>
                      )}

                      {/* Validate button + status */}
                      {keyInputValue && (
                        <div className="flex items-center gap-2 flex-wrap">
                          <button
                            type="button"
                            onClick={handleValidateKey}
                            disabled={keyValidation === 'validating'}
                            className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider border border-[var(--fd-text-faint)] text-[var(--fd-text-dim)] hover:border-[var(--fd-text-dim)] hover:text-[var(--fd-text-secondary)] transition-colors disabled:opacity-50"
                          >
                            {keyValidation === 'validating' ? t('settings.aiKeyValidating') : t('settings.aiKeyValidate')}
                          </button>
                          {keyValidation === 'valid' && (
                            <span className="text-[10px] text-[#107c10]">✓ {t('settings.aiKeyValid')}</span>
                          )}
                          {keyValidation === 'invalid' && (
                            <span className="text-[10px] text-red-400">✗ {t('settings.aiKeyInvalid')}</span>
                          )}
                          {keyValidation === 'unverifiable' && (
                            <span className="text-[10px] text-[#d4a200]">⚠ {t('settings.aiKeyUnverifiable')}</span>
                          )}
                        </div>
                      )}

                      {/* Privacy notice */}
                      <p className="text-xs text-yellow-400 flex items-center gap-1.5">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM12 17c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zM9 8V6c0-1.66 1.34-3 3-3s3 1.34 3 3v2H9z" />
                        </svg>
                        {t('settings.aiPrivacyNotice')}
                      </p>
                    </div>
                  ) : (
                    <p className="text-xs text-[#666] pt-2">{t('settings.aiSelectProviderHint')}</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </SectionCard>
      )}

      {/* Display */}
      <SectionCard title={t('settings.sectionDisplay')}>
        <SettingItem label={t('settings.theme')} description={t('settings.themeDesc')}>
          <select className={SELECT_CLS}>
            <option>{t('settings.themeDark')}</option>
            <option disabled>{t('settings.themeLight')} — {t('settings.comingSoon')}</option>
          </select>
        </SettingItem>
        <SettingItem label={t('settings.tableDensity')} description={t('settings.tableDensityDesc')}>
          <select className={SELECT_CLS}>
            <option>{t('settings.densityNormal')}</option>
            <option>{t('settings.densityCompact')}</option>
          </select>
        </SettingItem>
      </SectionCard>

      {/* Data */}
      <SectionCard title={t('settings.sectionData')}>
        <SettingItem label={t('settings.refreshInterval')} description={t('settings.refreshIntervalDesc')}>
          <select className={SELECT_CLS}>
            <option value="30">{t('settings.interval30s')}</option>
            <option value="60">{t('settings.interval1m')}</option>
            <option value="300">{t('settings.interval5m')}</option>
            <option value="0">{t('settings.intervalManual')}</option>
          </select>
        </SettingItem>
        <SettingItem label={t('settings.marketIndices')} description={t('settings.marketIndicesDesc')}>
          <div className="flex justify-end">
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked />
              <div className="w-9 h-5 bg-[var(--fd-rule)] peer-focus:ring-1 peer-focus:ring-[var(--color-accent)] rounded-full peer peer-checked:bg-[var(--color-accent)] transition-colors after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-[var(--fd-text-dim)] after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full peer-checked:after:bg-white" />
            </label>
          </div>
        </SettingItem>
        <SettingItem label={t('settings.topMovers')} description={t('settings.topMoversDesc')}>
          <div className="flex justify-end">
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked />
              <div className="w-9 h-5 bg-[var(--fd-rule)] peer-focus:ring-1 peer-focus:ring-[var(--color-accent)] rounded-full peer peer-checked:bg-[var(--color-accent)] transition-colors after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-[var(--fd-text-dim)] after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full peer-checked:after:bg-white" />
            </label>
          </div>
        </SettingItem>
      </SectionCard>

      {/* Notifications */}
      <SectionCard title={t('settings.sectionNotifications')}>
        <SettingItem
          label={t('settings.browserPush', 'Browser push notifications')}
          description={t('settings.browserPushDesc', 'Get alerts and agent briefs as desktop/mobile notifications, even when FlowDesktop is closed.')}
        >
          <div className="flex justify-end">
            <PushToggle />
          </div>
        </SettingItem>
        <NotificationPrefsPanel />
      </SectionCard>

      {/* About */}
      <SectionCard title={t('settings.sectionAbout')}>
        <SettingItem label={t('settings.version')}>
          <span className="text-sm text-[var(--fd-text-dim)]">v1.0.0</span>
        </SettingItem>

      </SectionCard>

      {/* Avatar "Apply" reminder modal */}
      <Modal
        isOpen={showAvatarWarning}
        onClose={() => setShowAvatarWarning(false)}
        title={t('settings.avatarApplyWarningTitle')}
        actions={
          <button
            className="px-4 py-1.5 text-sm font-semibold bg-[var(--color-accent)] text-white hover:bg-[#106ebe] transition-colors"
            onClick={() => setShowAvatarWarning(false)}
          >
            {t('settings.avatarApplyWarningOk')}
          </button>
        }
      >
        <div className="flex gap-3 items-start">
          <svg className="shrink-0 mt-0.5" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="square" strokeLinejoin="miter">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <p className="text-sm text-[var(--fd-text-secondary)] leading-relaxed">
            {t('settings.avatarApplyWarningBody')}
          </p>
        </div>
      </Modal>
    </div>
  )
}
