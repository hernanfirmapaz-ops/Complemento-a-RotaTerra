import { useState, useEffect } from 'react'
import type { AgronomicToolkitOut, RunoffRunOut, ScenarioComparisonOut, TerrainOut } from '../../types/api'
import type { AgronomistOverlayMode } from '../TerrainDiorama3D'
import { Metric } from '../ui/Metric'
import { OptionList, type OptionListItem } from '../ui/OptionList'
import { Details } from '../ui/Details'
import { Button } from '../ui/Button'
import { SourceNote } from '../ui/SourceNote'
import { Icon } from '../ui/Icon'
import { formatAmcLabel } from '../../utils/formatters'

interface ResultStepProps {
  stormMm: number
  run: RunoffRunOut | null
  runsList?: RunoffRunOut[]
  toolkit: AgronomicToolkitOut | null
  terrain: TerrainOut | null
  field?: { area_ha?: number } | null
  activeOverlay: AgronomistOverlayMode
  onSelectOverlay: (overlay: AgronomistOverlayMode) => void
  onReplayRain: () => void
  onChangeLot: () => void
  onCompareRuns?: (runAId: string, runBId: string) => Promise<ScenarioComparisonOut | null>
  onActivateRun?: (runId: string) => void
  onSimulatePresets?: () => Promise<void>
  busy: boolean
  className?: string
}

export function ResultStep({
  stormMm,
  run,
  runsList = [],
  toolkit,
  terrain,
  field,
  activeOverlay,
  onSelectOverlay,
  onReplayRain,
  onChangeLot,
  onCompareRuns,
  onActivateRun,
  onSimulatePresets,
  busy,
  className = '',
}: ResultStepProps) {
  const [showConfidenceDetails, setShowConfidenceDetails] = useState(false)
  const [showCompare, setShowCompare] = useState(false)
  const [compareA, setCompareA] = useState<string>('')
  const [compareB, setCompareB] = useState<string>('')
  const [comparison, setComparison] = useState<ScenarioComparisonOut | null>(null)
  const [comparing, setComparing] = useState(false)

  // Indicador de confianza (SDD-003 §3)
  const confidence = run?.confidence
  const confLevel = confidence?.level ?? 'medio'
  const confScore = confidence ? Math.round(confidence.score * 100) : null

  // Cálculo de métricas
  const runoffCoeff = run?.cn_result?.runoff_coefficient ?? null
  const runoffPct = runoffCoeff !== null ? Math.round(runoffCoeff * 100) : null

  // Estimación de porcentaje y hectáreas anegadas calculadas por la API (Issue #85)
  const pondedPct =
    run?.ponded_area_pct ??
    run?.hydrodynamic_2d_summary?.ponded_area_pct ??
    null
  const floodedHa =
    run?.hydrodynamic_2d_summary?.ponded_area_in_field_ha ?? null
  const totalFieldHa = run?.field_area_ha ?? field?.area_ha ?? null

  const pondedCaption =
    floodedHa !== null && totalFieldHa !== null
      ? `${floodedHa.toFixed(1).replace('.', ',')} ha de ${Math.round(totalFieldHa)} ha`
      : floodedHa !== null
        ? `${floodedHa.toFixed(1).replace('.', ',')} ha`
        : 'Sin simulación 2D'

  const waterloggingMeta =
    pondedPct !== null && floodedHa !== null && totalFieldHa !== null
      ? `${pondedPct.toFixed(1).replace('.', ',')} % (${floodedHa.toFixed(1).replace('.', ',')} ha de ${Math.round(totalFieldHa)} ha)`
      : floodedHa !== null
        ? `${floodedHa.toFixed(1).replace('.', ',')} ha`
        : 'Sin dato'

  // Pérdida de suelo USLE estimada en t/ha
  const soilLossAvg = toolkit?.erosion_usle?.mean_soil_loss_t_ha ?? null

  const extInflowM3 = run?.spatial_summary?.external_runoff_inflow_m3 ?? 0
  const fieldGeneratedM3 = run?.spatial_summary?.field_runoff_generated_m3 ?? 0

  const runoffCaption = extInflowM3 > 0
    ? `${Math.round(fieldGeneratedM3).toLocaleString('es-AR')} m³ lote + ${Math.round(extInflowM3).toLocaleString('es-AR')} m³ cuenca vecina`
    : run ? `${Math.round(fieldGeneratedM3).toLocaleString('es-AR')} m³ agua` : 'Sin simulación'

  // Opciones de capas en el visor 3D
  const layerOptions: OptionListItem[] = [
    {
      id: 'waterlogging',
      title: 'Dónde se encharca',
      subtitle: 'Lámina de agua acumulada en bajos y microrelieves',
      meta: waterloggingMeta,
      icon: 'droplet',
      selected: activeOverlay === 'waterlogging',
    },
    {
      id: 'satellite_water',
      title: 'Por dónde escurre',
      subtitle: 'Líneas y cañadones de concentración de flujo',
      meta: runoffPct !== null ? `${runoffPct}% escurre` : 'Sin dato',
      icon: 'compass',
      selected: activeOverlay === 'satellite_water',
    },
    {
      id: 'erosion',
      title: 'Pérdida de suelo y cárcavas',
      subtitle: 'Riesgo de erosión hídrica superficial (USLE)',
      meta: soilLossAvg !== null ? `${soilLossAvg.toFixed(1)} t/ha` : 'Sin dato',
      icon: 'alert-circle',
      selected: activeOverlay === 'erosion',
    },
    {
      id: 'environments',
      title: 'Ambientes y relieve natural',
      subtitle: 'Lomas altas, medias lomas y bajos de drenaje',
      icon: 'layers',
      selected: activeOverlay === 'environments',
    },
  ]

  // Configuración de comparación entre dos corridas
  const availableRuns = runsList.length > 0 ? runsList : (run ? [run] : [])
  const effCompareA = compareA || run?.id || availableRuns[0]?.id || ''
  const effCompareB = compareB || (availableRuns.find((r) => r.id !== effCompareA)?.id ?? availableRuns[1]?.id ?? '')

  useEffect(() => {
    if (showCompare && effCompareA && effCompareB && effCompareA !== effCompareB && onCompareRuns) {
      let active = true
      setComparing(true)
      onCompareRuns(effCompareA, effCompareB)
        .then((res) => {
          if (active) setComparison(res)
        })
        .finally(() => {
          if (active) setComparing(false)
        })
      return () => {
        active = false
      }
    } else {
      setComparison(null)
    }
  }, [showCompare, effCompareA, effCompareB, onCompareRuns])

  return (
    <div className={`result-step ${className}`}>
      {/* Encabezado con Indicador de Confianza (SDD-003 §3) */}
      <div className="result-header-with-confidence">
        <div className="step-header">
          <h2 className="step-heading">Qué pasó con {stormMm} mm</h2>
          <p className="step-subtext">
            Resultados de escurrimiento superficial, retención en bajos y balance hídrico para tu lote.
          </p>
        </div>

        <div className="confidence-chip-container">
          <button
            type="button"
            className={`confidence-chip confidence-chip-${confLevel}`}
            onClick={() => setShowConfidenceDetails(!showConfidenceDetails)}
            aria-expanded={showConfidenceDetails}
          >
            <span className="confidence-chip-dot" />
            <span className="confidence-chip-text">
              Indicador de confianza: {confLevel === 'alto' ? 'Alto' : confLevel === 'bajo' ? 'Bajo' : 'Medio'} · DEM {terrain?.source?.nominal_resolution_m ?? 30} m
            </span>
            <Icon name={showConfidenceDetails ? 'chevron-up' : 'chevron-down'} size={14} />
          </button>

          {showConfidenceDetails && (
            <div className="confidence-panel">
              <div className="confidence-panel-header">
                Fundamento técnico del cálculo ({confScore !== null ? `${confScore}%` : 'Sin dato'}):
              </div>
              <ul className="confidence-reasons-list">
                {(confidence?.reasons ?? [
                  'Relieve satelital Copernicus 30 m (precisión vertical ±2 m)',
                  'Suelo por omisión, sin confirmar',
                  'Tormenta de diseño regional basada en curva IDF transpuesta',
                ]).map((reason, idx) => (
                  <li key={idx}>{reason}</li>
                ))}
              </ul>
              <div className="confidence-notes-row">
                <div><strong>Relieve:</strong> {confidence?.relief_note ?? 'Copernicus GLO-30 (30 m)'}</div>
                <div><strong>Suelo:</strong> {confidence?.soil_note ?? 'Suelo por omisión, sin confirmar'}</div>
                <div><strong>Lluvia:</strong> {confidence?.rain_note ?? 'Diseño regional IDF INA'}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3 Métricas destacadas */}
      <div className="result-metrics-grid">
        <Metric
          value={
            pondedPct !== null
              ? pondedPct.toFixed(1).replace('.', ',')
              : 'Sin dato'
          }
          unit={pondedPct !== null ? '%' : undefined}
          label="Superficie anegable"
          caption={pondedCaption}
        />

        <Metric
          value={runoffPct !== null ? runoffPct : 'Sin dato'}
          unit={runoffPct !== null ? '%' : undefined}
          label="Escurre fuera del lote"
          caption={runoffCaption}
        />

        <Metric
          value={soilLossAvg !== null ? soilLossAvg.toFixed(1) : 'Sin dato'}
          unit={soilLossAvg !== null ? 't/ha' : undefined}
          label="Pérdida de suelo"
          caption={soilLossAvg !== null ? 'Erosión estimada por USLE' : 'Sin estimación de erosión USLE'}
        />
      </div>

      {/* Selector de capas visuales */}
      <div className="result-layers-section">
        <label className="field-label-text">Explorar en el visor 3D:</label>
        <OptionList
          items={layerOptions}
          onSelect={(item) => onSelectOverlay(item.id as AgronomistOverlayMode)}
        />
      </div>

      {/* Comparador de escenarios lado a lado (SDD-003 §4) */}
      <div className="result-compare-section">
        <Button
          variant="secondary"
          onClick={() => setShowCompare(!showCompare)}
          icon="sliders"
          fullWidth
        >
          {showCompare ? 'Ocultar comparador de escenarios' : 'Comparar con otro manejo o lluvia'}
        </Button>

        {showCompare && (
          <div className="scenario-compare-panel">
            <div className="compare-selectors-grid">
              <div className="compare-select-field">
                <label className="compare-field-label">Escenario Base (A):</label>
                <select
                  className="ui-select"
                  value={effCompareA}
                  onChange={(e) => setCompareA(e.target.value)}
                  disabled={busy || comparing}
                >
                  {availableRuns.map((r) => (
                    <option key={`a-${r.id}`} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="compare-select-field">
                <label className="compare-field-label">Comparar con (B):</label>
                <select
                  className="ui-select"
                  value={effCompareB}
                  onChange={(e) => setCompareB(e.target.value)}
                  disabled={busy || comparing}
                >
                  {availableRuns.map((r) => (
                    <option key={`b-${r.id}`} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {comparing && (
              <div style={{ fontSize: 12, color: 'var(--ink-2)', textAlign: 'center', padding: '6px 0' }}>
                Calculando diferencias hidrológicas...
              </div>
            )}

            {comparison && !comparing && (
              <>
                <div className="compare-deltas-grid">
                  <div className="compare-delta-card">
                    <span className="delta-label">Δ Superficie anegable</span>
                    {comparison.delta_ponded_area_ha !== null && comparison.delta_ponded_area_ha !== undefined ? (
                      <span className={`delta-val ${comparison.delta_ponded_area_ha < 0 ? 'is-negative' : comparison.delta_ponded_area_ha > 0 ? 'is-positive' : ''}`}>
                        {comparison.delta_ponded_area_ha > 0 ? `+${comparison.delta_ponded_area_ha}` : comparison.delta_ponded_area_ha} ha
                      </span>
                    ) : (
                      <>
                        <span className="delta-val is-muted">Sin dato</span>
                        <span className="delta-subval">Sin simulación 2D</span>
                      </>
                    )}
                  </div>

                  <div className="compare-delta-card">
                    <span className="delta-label">Δ Escurrimiento fuera</span>
                    {comparison.delta_runoff_pct !== null && comparison.delta_runoff_pct !== undefined ? (
                      <>
                        <span className={`delta-val ${comparison.delta_runoff_pct < 0 ? 'is-negative' : comparison.delta_runoff_pct > 0 ? 'is-positive' : ''}`}>
                          {comparison.delta_runoff_pct > 0 ? `+${comparison.delta_runoff_pct}` : comparison.delta_runoff_pct} %
                        </span>
                        {comparison.delta_runoff_volume_m3 !== undefined && (
                          <span className="delta-subval">
                            {(comparison.delta_runoff_volume_m3 ?? 0) > 0 ? `+${Math.round(comparison.delta_runoff_volume_m3).toLocaleString('es-AR')}` : Math.round(comparison.delta_runoff_volume_m3).toLocaleString('es-AR')} m³
                          </span>
                        )}
                      </>
                    ) : (
                      <>
                        <span className={`delta-val ${(comparison.delta_runoff_volume_m3 ?? 0) < 0 ? 'is-negative' : (comparison.delta_runoff_volume_m3 ?? 0) > 0 ? 'is-positive' : ''}`}>
                          {(comparison.delta_runoff_volume_m3 ?? 0) > 0
                            ? `+${Math.round(comparison.delta_runoff_volume_m3 ?? 0).toLocaleString('es-AR')} m³`
                            : `${Math.round(comparison.delta_runoff_volume_m3 ?? 0).toLocaleString('es-AR')} m³`}
                        </span>
                        <span className="delta-subval">base 0 mm</span>
                      </>
                    )}
                  </div>

                  <div className="compare-delta-card">
                    <span className="delta-label">Δ Pérdida de suelo</span>
                    {comparison.delta_soil_loss_t_ha !== null && comparison.delta_soil_loss_t_ha !== undefined ? (
                      <span className={`delta-val ${comparison.delta_soil_loss_t_ha < 0 ? 'is-negative' : comparison.delta_soil_loss_t_ha > 0 ? 'is-positive' : ''}`}>
                        {comparison.delta_soil_loss_t_ha > 0 ? `+${comparison.delta_soil_loss_t_ha}` : comparison.delta_soil_loss_t_ha} t/ha
                      </span>
                    ) : (
                      <>
                        <span className="delta-val is-muted">Sin dato</span>
                        <span className="delta-subval">Sin datos USLE</span>
                      </>
                    )}
                  </div>
                </div>

                {comparison.summary_text && (
                  <div className="compare-summary-box">
                    {comparison.summary_text}
                  </div>
                )}

                {comparison.notes && comparison.notes.length > 0 && (
                  <div className="compare-notes-list" style={{ fontSize: 11, color: 'var(--ink-2)', marginTop: 6, lineHeight: 1.4 }}>
                    {comparison.notes.map((note, idx) => (
                      <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span style={{ opacity: 0.7 }}>•</span>
                        <span>{note}</span>
                      </div>
                    ))}
                  </div>
                )}

                {onActivateRun && (
                  effCompareB && effCompareB !== run?.id ? (
                    <Button
                      variant="text"
                      size="sm"
                      onClick={() => onActivateRun(effCompareB)}
                      disabled={busy}
                    >
                      Ver escenario B en el visor 3D →
                    </Button>
                  ) : effCompareA && effCompareA !== run?.id ? (
                    <Button
                      variant="text"
                      size="sm"
                      onClick={() => onActivateRun(effCompareA)}
                      disabled={busy}
                    >
                      Ver escenario A en el visor 3D →
                    </Button>
                  ) : null
                )}
              </>
            )}

            {effCompareA === effCompareB && (
              <div style={{ fontSize: 11.5, color: 'var(--ink-3)', textAlign: 'center' }}>
                Elegí dos escenarios diferentes para ver las diferencias numéricas.
              </div>
            )}

            {onSimulatePresets && (
              <div className="compare-presets-cta">
                <Button
                  variant="secondary"
                  size="sm"
                  fullWidth
                  onClick={onSimulatePresets}
                  disabled={busy || comparing}
                >
                  Generar escenarios estándar (30, 80 y 130 mm)
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Detalles técnicos plegables con caudales y láminas */}
      <div className="result-details-accordion">
        <Details
          summary="Ver detalles técnicos del cálculo"
          subsummary="CN, Manning, caudales y láminas"
        >
          <div className="result-tech-table">
            <div className="tech-row">
              <span>Curva Número (CN):</span>
              <strong>{run?.cn_result?.cn_effective ?? 'Sin dato'}</strong>
            </div>
            <div className="tech-row">
              <span>Lámina de escorrentía directa Q:</span>
              <strong>{run?.cn_result?.runoff_q_mm !== undefined && run?.cn_result?.runoff_q_mm !== null ? `${run.cn_result.runoff_q_mm.toFixed(1)} mm` : 'Sin dato'}</strong>
            </div>
            {run?.spatial_summary?.peak_discharge_m3_s !== undefined && run?.spatial_summary?.peak_discharge_m3_s !== null && (
              <div className="tech-row">
                <span>Caudal pico estimado:</span>
                <strong>{run.spatial_summary.peak_discharge_m3_s.toFixed(2)} m³/s</strong>
              </div>
            )}
            {extInflowM3 > 0 && (
              <div className="tech-row">
                <span>Aporte cuenca externa (buffer):</span>
                <strong>{Math.round(extInflowM3).toLocaleString('es-AR')} m³</strong>
              </div>
            )}
            <div className="tech-row">
              <span>Humedad Antecedente (AMC):</span>
              <strong>{formatAmcLabel(run?.cn_result?.antecedent_moisture)}</strong>
            </div>
            <div className="tech-row">
              <span>Resolución DEM:</span>
              <strong>{terrain?.source?.nominal_resolution_m ?? 30} m ({terrain?.source?.source_id === 'copernicus_glo30' ? 'Copernicus GLO-30' : 'Relieve local'})</strong>
            </div>
            <div className="tech-row">
              <span>Enrutamiento:</span>
              <strong>Freeman MFD (exponente 1.1)</strong>
            </div>
          </div>
        </Details>

        <Details
          summary="Fuentes y límites de los datos"
          subsummary="Transparencia"
        >
          <div className="result-sources-content">
            <SourceNote
              source="Copernicus GLO-30"
              details="Resolución 30 m · Precisión vertical ±2 m"
              disclaimer="Agencia Espacial Europea (ESA)"
            />
            <SourceNote
              source="NASA POWER"
              details="Cuadrícula ~55 km · Precipitaciones diarias históricas"
            />
            <SourceNote
              source="Servicio Meteorológico Nacional (SMN)"
              details="Referencia geográfica de estación provincial"
            />
            <SourceNote
              isNotice
              source=""
              disclaimer="Aviso legal: los resultados son modelos matemáticos para soporte a la toma de decisiones y no constituyen garantía hidrológica ante eventos extraordinarios."
            />
          </div>
        </Details>
      </div>

      {/* Acciones para continuar o cambiar */}
      <div className="result-footer-actions">
        <Button
          variant="primary"
          onClick={onReplayRain}
          disabled={busy}
          fullWidth
        >
          Probar otra lluvia
        </Button>
        <Button
          variant="text"
          onClick={onChangeLot}
          disabled={busy}
        >
          ← Cambiar de lote
        </Button>
      </div>
    </div>
  )
}
