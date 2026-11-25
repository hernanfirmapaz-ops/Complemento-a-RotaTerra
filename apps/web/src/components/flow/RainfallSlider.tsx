import React, { useId, useMemo, useState } from 'react'
import type { RainfallLadderOut } from '../../types/api'
import { formatDecimal, formatHa } from '../../utils/formatters'

export interface RainfallSliderProps {
  value: number
  onChange: (mm: number) => void
  ladderData?: RainfallLadderOut | null
  loadingLadder?: boolean
  disabled?: boolean
  className?: string
}

export function RainfallSlider({
  value,
  onChange,
  ladderData,
  loadingLadder = false,
  disabled = false,
  className = '',
}: RainfallSliderProps) {
  const inputId = useId()
  const [inputText, setInputText] = useState<string>(() => formatDecimal(value, 0))
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null)

  // Sincronizar input de texto cuando cambia el valor externo
  React.useEffect(() => {
    setInputText(formatDecimal(value, 0))
  }, [value])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value
    setInputText(raw)
    const normalized = raw.replace(',', '.')
    const parsed = parseFloat(normalized)
    if (!isNaN(parsed) && parsed >= 5 && parsed <= 150) {
      onChange(Math.round(parsed * 2) / 2)
    }
  }

  const handleInputBlur = () => {
    const normalized = inputText.replace(',', '.')
    let parsed = parseFloat(normalized)
    if (isNaN(parsed)) parsed = value
    parsed = Math.min(150, Math.max(5, parsed))
    onChange(parsed)
    setInputText(formatDecimal(parsed, 0))
  }

  // Ticks de períodos de retorno REM si están en rango (< 40 km)
  const returnPeriods = ladderData?.return_periods_station
  const ticks = useMemo(() => {
    if (!returnPeriods) return []
    const m = returnPeriods.milimetros ?? {
      T2: (returnPeriods as any).t2_mm,
      T10: (returnPeriods as any).t10_mm,
      T25: (returnPeriods as any).t25_mm,
      T50: (returnPeriods as any).t50_mm,
    }
    if (!m) return []
    const list: { key: string; label: string; mm: number; tooltip: string }[] = []
    const keys: ('T2' | 'T10' | 'T25' | 'T50')[] = ['T2', 'T10', 'T25', 'T50']
    const yearLabels: Record<string, string> = {
      T2: '2',
      T10: '10',
      T25: '25',
      T50: '50',
    }

    for (const k of keys) {
      const mmVal = m[k]
      if (typeof mmVal === 'number' && mmVal >= 5 && mmVal <= 150) {
        list.push({
          key: k,
          label: k,
          mm: mmVal,
          tooltip: `Evento con recurrencia promedio de ${yearLabels[k]} años (${formatDecimal(mmVal, 1)} mm en un día). Fuente: ${returnPeriods.station_name || (returnPeriods as any).name || 'REM San Luis'} (${returnPeriods.method || (returnPeriods as any).source || 'Gumbel'}).`,
        })
      }
    }
    return list
  }, [returnPeriods])

  // Estimación de hectáreas anegadas para el valor actual a partir de la escalera
  const currentPondedHa = useMemo(() => {
    if (!ladderData?.ladder || ladderData.ladder.length === 0) return null
    const steps = ladderData.ladder
    // Si coincide con un peldaño exacto
    const exact = steps.find((s) => Math.abs(s.precipitation_mm - value) < 0.5)
    if (exact) return exact.ponded_area_ha

    // Interpolación lineal entre los dos peldaños vecinos
    if (value <= steps[0].precipitation_mm) return steps[0].ponded_area_ha
    if (value >= steps[steps.length - 1].precipitation_mm) return steps[steps.length - 1].ponded_area_ha

    for (let i = 0; i < steps.length - 1; i++) {
      const s0 = steps[i]
      const s1 = steps[i + 1]
      if (value >= s0.precipitation_mm && value <= s1.precipitation_mm) {
        const factor = (value - s0.precipitation_mm) / (s1.precipitation_mm - s0.precipitation_mm)
        return s0.ponded_area_ha + factor * (s1.ponded_area_ha - s0.ponded_area_ha)
      }
    }
    return null
  }, [ladderData, value])

  const critThreshold = ladderData?.critical_ponding_threshold_mm ?? null

  return (
    <div className={`rainfall-slider-box ${className}`} style={{ marginTop: '0.75rem', marginBottom: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <label htmlFor={inputId} style={{ fontWeight: 600, fontSize: '0.9rem', color: '#1e293b' }}>
          Lámina de precipitación acumulada:
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <input
            id={inputId}
            type="text"
            inputMode="decimal"
            value={inputText}
            onChange={handleInputChange}
            onBlur={handleInputBlur}
            disabled={disabled}
            style={{
              width: '64px',
              padding: '0.25rem 0.4rem',
              textAlign: 'right',
              fontSize: '1rem',
              fontWeight: 700,
              color: '#0f172a',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              backgroundColor: disabled ? '#f1f5f9' : '#ffffff',
            }}
          />
          <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#475569' }}>mm</span>
        </div>
      </div>

      {/* Control Deslizador con marcas de períodos de retorno */}
      <div style={{ position: 'relative', width: '100%', padding: '0.5rem 0' }}>
        <input
          type="range"
          min="5"
          max="150"
          step="5"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          disabled={disabled}
          style={{
            width: '100%',
            height: '8px',
            borderRadius: '4px',
            accentColor: '#2563eb',
            cursor: disabled ? 'not-allowed' : 'pointer',
          }}
        />

        {/* Ticks de retorno T2..T50 */}
        {ticks.length > 0 && (
          <div style={{ position: 'relative', width: '100%', height: '24px', marginTop: '-4px' }}>
            {ticks.map((t) => {
              const leftPct = ((t.mm - 5) / (150 - 5)) * 100
              const isHovered = activeTooltip === t.key
              return (
                <div
                  key={t.key}
                  style={{
                    position: 'absolute',
                    left: `${leftPct}%`,
                    transform: 'translateX(-50%)',
                    textAlign: 'center',
                    cursor: 'pointer',
                  }}
                  onClick={() => onChange(Math.round(t.mm))}
                  onMouseEnter={() => setActiveTooltip(t.key)}
                  onMouseLeave={() => setActiveTooltip(null)}
                >
                  <div style={{ width: '2px', height: '6px', backgroundColor: '#64748b', margin: '0 auto' }} />
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      color: Math.abs(value - t.mm) < 3 ? '#2563eb' : '#64748b',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {t.label}
                  </span>

                  {/* Tooltip flotante con fuente real "en un día" */}
                  {isHovered && (
                    <div
                      style={{
                        position: 'absolute',
                        bottom: '26px',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        backgroundColor: '#1e293b',
                        color: '#f8fafc',
                        padding: '0.4rem 0.6rem',
                        borderRadius: '6px',
                        fontSize: '0.75rem',
                        lineHeight: 1.3,
                        width: '210px',
                        zIndex: 30,
                        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.2)',
                        pointerEvents: 'none',
                        textAlign: 'left',
                      }}
                    >
                      {t.tooltip}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Mini-gráfico interactivo: Hectáreas anegadas vs. mm de lluvia */}
      {ladderData?.ladder && ladderData.ladder.length > 0 ? (
        <div
          style={{
            marginTop: '0.75rem',
            padding: '0.6rem',
            backgroundColor: '#f8fafc',
            borderRadius: '8px',
            border: '1px solid #e2e8f0',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#334155' }}>
              Curva de anegamiento del lote (ha vs mm):
            </span>
            {currentPondedHa !== null && (
              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#2563eb' }}>
                {formatHa(currentPondedHa, 2)} anegadas ({formatDecimal((currentPondedHa / (ladderData.ladder[ladderData.ladder.length - 1].ponded_area_ha || 1)) * 100, 1)} %)
              </span>
            )}
          </div>

          <MiniPondingChart
            steps={ladderData.ladder}
            currentMm={value}
            criticalMm={critThreshold}
            onSelectMm={onChange}
          />

          {critThreshold !== null && (
            <div style={{ marginTop: '0.35rem', fontSize: '0.72rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#dc2626' }} />
              <span>
                <strong>Umbral crítico de anegamiento: P ≈ {formatDecimal(critThreshold, 0)} mm.</strong> A partir de este valor, la retención en cubetas se satura y el escurrimiento invade sectores productivos.
              </span>
            </div>
          )}
        </div>
      ) : loadingLadder ? (
        <div style={{ marginTop: '0.5rem', fontSize: '0.78rem', color: '#64748b', fontStyle: 'italic' }}>
          Calculando escalera de anegamiento en segundo plano…
        </div>
      ) : null}
    </div>
  )
}

/**
 * Mini-gráfico SVG responsivo de superficie anegada vs precipitación (Spec 031 §3.2).
 */
function MiniPondingChart({
  steps,
  currentMm,
  criticalMm,
  onSelectMm,
}: {
  steps: { precipitation_mm: number; ponded_area_ha: number }[]
  currentMm: number
  criticalMm: number | null
  onSelectMm: (mm: number) => void
}) {
  const width = 320
  const height = 80
  const padX = 24
  const padY = 12

  const maxP = 150
  const maxHa = Math.max(0.1, ...steps.map((s) => s.ponded_area_ha)) * 1.15

  const points = steps.map((s) => {
    const x = padX + ((s.precipitation_mm - 5) / (maxP - 5)) * (width - 2 * padX)
    const y = height - padY - (s.ponded_area_ha / maxHa) * (height - 2 * padY)
    return { x, y, mm: s.precipitation_mm, ha: s.ponded_area_ha }
  })

  // Generar path SVG para la línea y el área bajo la curva
  const linePath = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
  const areaPath = `${linePath} L ${points[points.length - 1].x.toFixed(1)} ${height - padY} L ${points[0].x.toFixed(1)} ${height - padY} Z`

  // Coordenadas del punto activo actual
  const currentX = padX + ((Math.min(150, Math.max(5, currentMm)) - 5) / (maxP - 5)) * (width - 2 * padX)
  const critX = criticalMm ? padX + ((Math.min(150, Math.max(5, criticalMm)) - 5) / (maxP - 5)) * (width - 2 * padX) : null

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      style={{ width: '100%', height: '70px', display: 'block', overflow: 'visible', cursor: 'crosshair' }}
      onClick={(e) => {
        const rect = e.currentTarget.getBoundingClientRect()
        const clickX = e.clientX - rect.left
        const relX = (clickX / rect.width) * width
        const mmClicked = 5 + ((relX - padX) / (width - 2 * padX)) * (maxP - 5)
        onSelectMm(Math.min(150, Math.max(5, Math.round(mmClicked / 5) * 5)))
      }}
    >
      <defs>
        <linearGradient id="pondingAreaGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#93c5fd" stopOpacity="0.05" />
        </linearGradient>
      </defs>

      {/* Eje base */}
      <line x1={padX} y1={height - padY} x2={width - padX} y2={height - padY} stroke="#cbd5e1" strokeWidth="1" />

      {/* Área y curva de la escalera */}
      <path d={areaPath} fill="url(#pondingAreaGrad)" />
      <path d={linePath} fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

      {/* Puntos de peldaños */}
      {points.map((p) => (
        <circle key={p.mm} cx={p.x} cy={p.y} r="2.5" fill="#1d4ed8" />
      ))}

      {/* Línea vertical de umbral crítico */}
      {critX !== null && (
        <line
          x1={critX}
          y1={padY}
          x2={critX}
          y2={height - padY}
          stroke="#dc2626"
          strokeWidth="1.5"
          strokeDasharray="3 3"
        />
      )}

      {/* Marcador del punto activo */}
      <circle cx={currentX} cy={height - padY} r="4" fill="#0f172a" stroke="#ffffff" strokeWidth="1.5" />
      <line x1={currentX} y1={padY} x2={currentX} y2={height - padY} stroke="#0f172a" strokeWidth="1" strokeDasharray="2 2" opacity="0.6" />
    </svg>
  )
}
