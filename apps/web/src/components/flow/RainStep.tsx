import type { AntecedentMoisture, DailyRainfallContextOut, SoilOut } from '../../types/api'
import { Button } from '../ui/Button'
import { Segmented } from '../ui/Segmented'
import { Details } from '../ui/Details'
import { SourceNote } from '../ui/SourceNote'

interface RainStepProps {
  stormMm: number
  onSelectMm: (mm: number) => void
  amc: AntecedentMoisture
  onChangeAmc: (amc: AntecedentMoisture) => void
  coverCode: string
  onChangeCoverCode: (cover: string) => void
  dailyRainContext: DailyRainfallContextOut | null
  selectedDate: string
  onChangeSelectedDate: (date: string) => void
  onSimulateDailyDate: (date: string) => void
  onSimulate: () => void
  onBack: () => void
  busy: boolean
  soilInfo?: SoilOut | null
  className?: string
}

export function RainStep({
  stormMm,
  onSelectMm,
  amc,
  onChangeAmc,
  coverCode,
  onChangeCoverCode,
  dailyRainContext,
  selectedDate,
  onChangeSelectedDate,
  onSimulateDailyDate,
  onSimulate,
  onBack,
  busy,
  soilInfo = null,
  className = '',
}: RainStepProps) {
  const rainOptions = [
    { value: '30', label: 'Conservador 30 mm', sublabel: 'Lluvia suave' },
    { value: '80', label: 'Medio 80 mm', sublabel: 'Tormenta de diseño' },
    { value: '130', label: 'Crítico 130 mm', sublabel: 'Crecida extraordinaria' },
  ]

  return (
    <div className={`rain-step ${className}`}>
      <div className="step-header">
        <h2 className="step-heading">¿Cuánto llueve?</h2>
        <p className="step-subtext">
          Elegí el escenario de tormenta de diseño (Conservador, Medio o Crítico) para simular el escurrimiento y los bajos de retención.
        </p>
      </div>

      <div className="rain-presets-block">
        <label className="field-label-text">Intensidad de tormenta:</label>
        <Segmented
          value={String(stormMm)}
          onChange={(val) => onSelectMm(Number(val))}
          options={rainOptions}
          disabled={busy}
        />
      </div>

      {/* Más opciones técnicas plegadas */}
      <div className="rain-advanced-details">
        <Details
          summary="Más opciones (día real, suelo y manejo)"
          subsummary="Avanzado"
        >
          <div className="rain-advanced-content">
            {/* Día real de lluvia nacional */}
            {dailyRainContext && (
              <div className="rain-daily-box">
                <label className="field-sublabel">
                  Día real de lluvia satelital (NASA POWER ~55 km):
                </label>
                <div className="rain-daily-row">
                  <input
                    type="date"
                    className="ui-input-date"
                    value={selectedDate}
                    onChange={(e) => onChangeSelectedDate(e.target.value)}
                    disabled={busy}
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => onSimulateDailyDate(selectedDate)}
                    disabled={busy || !selectedDate}
                  >
                    Simular fecha
                  </Button>
                </div>
                {dailyRainContext.nearest_smn_station && (
                  <span className="rain-smn-ref">
                    Referencia geográfica: Estación SMN {dailyRainContext.nearest_smn_station.name} ({dailyRainContext.nearest_smn_station.distance_km} km)
                  </span>
                )}
              </div>
            )}

            {/* Estado previo del suelo */}
            <div className="rain-field-group">
              <label className="field-sublabel">
                Humedad antecedente en el perfil (AMC):
              </label>
              <select
                className="ui-select"
                value={amc}
                onChange={(e) => onChangeAmc(e.target.value as AntecedentMoisture)}
                disabled={busy}
              >
                <option value="dry">Seco (AMC I) — Suelo sediento, infiltra más</option>
                <option value="medium">Normal (AMC II) — Humedad media de campaña</option>
                <option value="wet">Húmedo (AMC III) — Suelo saturado por lluvias previas</option>
              </select>
            </div>

            {/* Cobertura / Manejo agrícola */}
            <div className="rain-field-group">
              <label className="field-sublabel">
                Manejo del cultivo y rastrojo:
              </label>
              <select
                className="ui-select"
                value={coverCode}
                onChange={(e) => onChangeCoverCode(e.target.value)}
                disabled={busy}
              >
                <option value="soja_maiz_sd_buena">
                  Siembra Directa continua (&gt;30% rastrojo) · Recomendado
                </option>
                <option value="soja_maiz_convencional">
                  Convencional con labranza / baja cobertura
                </option>
                <option value="cultivo_cobertura_vicia_centeno">
                  Cultivo de cobertura denso (Vicia / Centeno)
                </option>
                <option value="pastura_pradera_buena">
                  Pastura consociada perenne
                </option>
                <option value="barbecho_suelo_desnudo">
                  Barbecho limpio / suelo desnudo (alto riesgo)
                </option>
              </select>
            </div>
          </div>
        </Details>
      </div>

      {/* CTA principal */}
      <div className="rain-cta-stack">
        <Button
          variant="primary"
          onClick={onSimulate}
          loading={busy}
          fullWidth
        >
          Simular lluvia de {stormMm} mm
        </Button>
        <Button
          variant="text"
          onClick={onBack}
          disabled={busy}
        >
          ← Cambiar de lote
        </Button>
      </div>

      <div className="step-footer-note">
        <SourceNote
          source={
            soilInfo?.soil_group
              ? `Suelo ${soilInfo.texture_class?.toLowerCase() ?? ''} · grupo ${soilInfo.soil_group}`
              : 'Suelo sin confirmar · grupo B por omisión'
          }
          details={soilInfo?.soil_group ? soilInfo.source_label : 'No se pudo consultar una fuente de suelos'}
        />
        <SourceNote
          source="Curva Número (USDA-NRCS) y flujo MFD"
          details="Tormenta de diseño: escenario hipotético, no un evento medido"
        />
      </div>
    </div>
  )
}
