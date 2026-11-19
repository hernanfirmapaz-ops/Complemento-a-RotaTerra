import { useState } from 'react'
import type {
  ConditioningMode,
  HydrologyOut,
  HydrologyRunIn,
} from '../types/api'

interface Props {
  hasTerrain: boolean
  hydrology: HydrologyOut | null
  busy: boolean
  onRun: (params: HydrologyRunIn) => void
}

export function HydrologyPanel({
  hasTerrain,
  hydrology,
  busy,
  onRun,
}: Props) {
  const [mode, setMode] = useState<ConditioningMode>('fill_small')
  const [maxFillDepth, setMaxFillDepth] = useState<number>(0.35)
  const [maxFillArea, setMaxFillArea] = useState<number>(4500)
  const [mfdExp, setMfdExp] = useState<number>(1.1)
  const [routingBasis, setRoutingBasis] = useState<'MFD' | 'D8'>('MFD')
  const [thresholdHa, setThresholdHa] = useState<string>('')
  const [contourInterval, setContourInterval] = useState<string>('')

  const handleSubmit = () => {
    onRun({
      conditioning_mode: mode,
      max_fill_depth_m: maxFillDepth,
      max_fill_area_m2: maxFillArea,
      mfd_exponent: mfdExp,
      routing_basis: routingBasis,
      stream_threshold_ha:
        thresholdHa.trim() !== '' ? Number(thresholdHa) : null,
      contour_interval_m:
        contourInterval.trim() !== '' ? Number(contourInterval) : null,
    })
  }

  return (
    <section className="card">
      <h3>3. Hidrología estática (Fase 1 · D8 + MFD)</h3>

      <label className="field-label">
        Tratamiento de depresiones (SDD §6.2)
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as ConditioningMode)}
        >
          <option value="fill_small">
            Selectivo: rellenar solo micro-depresiones espurias (recomendado)
          </option>
          <option value="preserve">
            Conservar todas las depresiones como retenciones reales
          </option>
          <option value="fill_all">
            Relleno completo (Priority-Flood) para drenaje continuo
          </option>
        </select>
      </label>

      {mode === 'fill_small' && (
        <div className="two-cols">
          <label className="field-label">
            Prof. máx. relleno (m)
            <input
              type="number"
              min={0}
              max={5}
              step={0.05}
              value={maxFillDepth}
              onChange={(e) => setMaxFillDepth(Number(e.target.value))}
            />
          </label>
          <label className="field-label">
            Área máx. relleno (m²)
            <input
              type="number"
              min={0}
              max={500000}
              step={500}
              value={maxFillArea}
              onChange={(e) => setMaxFillArea(Number(e.target.value))}
            />
          </label>
        </div>
      )}

      <div className="two-cols">
        <label className="field-label">
          Base red de drenaje
          <select
            value={routingBasis}
            onChange={(e) =>
              setRoutingBasis(e.target.value as 'MFD' | 'D8')
            }
          >
            <option value="MFD">MFD (difuso laderas)</option>
            <option value="D8">D8 (concentrado)</option>
          </select>
        </label>
        <label className="field-label">
          Exponente MFD (p)
          <input
            type="number"
            min={0.5}
            max={5}
            step={0.1}
            value={mfdExp}
            onChange={(e) => setMfdExp(Number(e.target.value))}
          />
        </label>
      </div>

      <div className="two-cols">
        <label className="field-label">
          Umbral red (ha, vacío=auto)
          <input
            type="number"
            min={0.1}
            step={0.5}
            placeholder="Auto según escala"
            value={thresholdHa}
            onChange={(e) => setThresholdHa(e.target.value)}
          />
        </label>
        <label className="field-label">
          Curvas nivel (m, vacío=auto)
          <input
            type="number"
            min={0.5}
            step={0.5}
            placeholder="Auto"
            value={contourInterval}
            onChange={(e) => setContourInterval(e.target.value)}
          />
        </label>
      </div>

      <button
        className="btn-primary full-width"
        onClick={handleSubmit}
        disabled={!hasTerrain || busy}
      >
        {hydrology
          ? 'Recalcular hidrología estática'
          : 'Calcular D8, MFD, cuencas y depresiones'}
      </button>

      {hydrology && (
        <div className="hydro-summary">
          <dl className="kv-grid">
            <div>
              <dt>Acum. máx. MFD lote</dt>
              <dd>{hydrology.summary.max_mfd_area_in_field_ha.toFixed(2)} ha</dd>
            </div>
            <div>
              <dt>Acum. máx. D8 lote</dt>
              <dd>{hydrology.summary.max_d8_area_in_field_ha.toFixed(2)} ha</dd>
            </div>
            <div>
              <dt>Rutas drenaje (umbral {String(hydrology.parameters.stream_threshold_ha)} ha)</dt>
              <dd>
                {hydrology.summary.stream_segments_count} tramos (
                {hydrology.summary.total_stream_length_m.toFixed(0)} m)
              </dd>
            </div>
            <div>
              <dt>Aporte externo al lote</dt>
              <dd>{hydrology.summary.external_inflow_ha.toFixed(2)} ha</dd>
            </div>
            <div>
              <dt>Depresiones en lote</dt>
              <dd>
                {hydrology.summary.depressions_in_field_count} (
                {hydrology.summary.total_depression_area_in_field_ha.toFixed(2)}{' '}
                ha ·{' '}
                {hydrology.summary.total_depression_volume_in_field_m3.toFixed(
                  0,
                )}{' '}
                m³)
              </dd>
            </div>
            <div>
              <dt>Balance masa MFD</dt>
              <dd>
                error {(hydrology.summary.mfd_mass_balance_error * 100).toFixed(4)} %
              </dd>
            </div>
          </dl>
        </div>
      )}
    </section>
  )
}
