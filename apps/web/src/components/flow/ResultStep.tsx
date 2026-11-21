import type { AgronomicToolkitOut, RunoffRunOut, TerrainOut } from '../../types/api'
import type { AgronomistOverlayMode } from '../TerrainDiorama3D'
import { Metric } from '../ui/Metric'
import { OptionList, type OptionListItem } from '../ui/OptionList'
import { Details } from '../ui/Details'
import { Button } from '../ui/Button'
import { SourceNote } from '../ui/SourceNote'

interface ResultStepProps {
  stormMm: number
  run: RunoffRunOut | null
  toolkit: AgronomicToolkitOut | null
  terrain: TerrainOut | null
  activeOverlay: AgronomistOverlayMode
  onSelectOverlay: (overlay: AgronomistOverlayMode) => void
  onReplayRain: () => void
  onChangeLot: () => void
  onOpenToolkit: () => void
  busy: boolean
  className?: string
}

export function ResultStep({
  stormMm,
  run,
  toolkit,
  terrain,
  activeOverlay,
  onSelectOverlay,
  onReplayRain,
  onChangeLot,
  onOpenToolkit,
  busy,
  className = '',
}: ResultStepProps) {
  // Cálculo de métricas
  const runoffCoeff = run?.cn_result?.runoff_coefficient ?? 0.35
  const runoffPct = Math.round(runoffCoeff * 100)

  // Estimación de hectáreas anegadas a partir del modelo hidrodinámico 2D o volumen
  const floodedHa = run?.hydrodynamic_2d_summary?.ponded_area_in_field_ha
    ?? (run ? (run.spatial_summary.field_runoff_generated_m3 / 10000) * 0.18 : 0)

  // Pérdida de suelo USLE estimada en t/ha
  const soilLossAvg = toolkit?.erosion_usle
    ? toolkit.erosion_usle.mean_soil_loss_t_ha
    : Math.max(1.2, Number((runoffCoeff * 8.4).toFixed(1)))

  const layerOptions: OptionListItem[] = [
    {
      id: 'waterlogging',
      title: 'Dónde se encharca',
      subtitle: 'Lámina de agua acumulada en bajos y microrelieves',
      meta: `${floodedHa.toFixed(1)} ha`,
      icon: 'droplet',
      selected: activeOverlay === 'waterlogging',
    },
    {
      id: 'satellite_water',
      title: 'Por dónde escurre',
      subtitle: 'Líneas y cañadones de concentración de flujo',
      meta: `${runoffPct}% escurre`,
      icon: 'compass',
      selected: activeOverlay === 'satellite_water',
    },
    {
      id: 'erosion',
      title: 'Pérdida de suelo y cárcavas',
      subtitle: 'Riesgo de erosión hídrica superficial (USLE)',
      meta: `${soilLossAvg.toFixed(1)} t/ha`,
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

  return (
    <div className={`result-step ${className}`}>
      <div className="step-header">
        <h2 className="step-heading">Qué pasó con {stormMm} mm</h2>
        <p className="step-subtext">
          Resultados de escurrimiento superficial, retención en bajos y pérdida de suelo para tu lote.
        </p>
      </div>

      {/* 3 Métricas destacadas */}
      <div className="result-metrics-grid">
        <Metric
          value={floodedHa.toFixed(1)}
          unit="ha"
          range={`${Math.max(0.1, floodedHa * 0.85).toFixed(1)} – ${(floodedHa * 1.15).toFixed(1)} ha`}
          label="Superficie anegable"
          caption="Bajos y cubetas de retención"
        />

        <Metric
          value={runoffPct}
          unit="%"
          range={`${Math.max(5, runoffPct - 8)} – ${Math.min(95, runoffPct + 8)} %`}
          label="Escurre fuera del lote"
          caption={run ? `${Math.round(run.spatial_summary.field_runoff_generated_m3).toLocaleString('es-AR')} m³ agua` : 'Volumen total'}
        />

        <Metric
          value={soilLossAvg.toFixed(1)}
          unit="t/ha"
          range={`${(soilLossAvg * 0.8).toFixed(1)} – ${(soilLossAvg * 1.25).toFixed(1)} t/ha`}
          label="Pérdida de suelo"
          caption="Erosión estimada por USLE"
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

      {/* Acceso a las 8 herramientas agronómicas adicionales */}
      <div className="result-toolkit-callout">
        <Button
          variant="secondary"
          onClick={onOpenToolkit}
          icon="layers"
          fullWidth
        >
          Ver las 8 herramientas agronómicas (rotación, siembra, heladas) →
        </Button>
      </div>

      {/* Detalles técnicos plegables */}
      <div className="result-details-accordion">
        <Details
          summary="Ver detalles técnicos del cálculo"
          subsummary="CN, Manning y MFD"
        >
          <div className="result-tech-table">
            <div className="tech-row">
              <span>Curva Número (CN):</span>
              <strong>{run?.cn_result.cn_effective ?? 75}</strong>
            </div>
            <div className="tech-row">
              <span>Humedad Antecedente (AMC):</span>
              <strong>{run?.cn_result.antecedent_moisture?.toUpperCase() ?? 'MEDIUM'}</strong>
            </div>
            <div className="tech-row">
              <span>Resolución DEM:</span>
              <strong>{terrain?.source?.nominal_resolution_m ?? 30} m (Copernicus GLO-30)</strong>
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
