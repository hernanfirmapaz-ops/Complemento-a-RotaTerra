import { useState } from 'react'
import type {
  AntecedentMoisture,
  RainfallEventManualIn,
  RainfallEventOut,
  RainfallSourceType,
  RunoffRunIn,
  RunoffRunOut,
  ScenarioComparisonOut,
  SoilGroup,
} from '../types/api'

interface Props {
  hasTerrain: boolean
  events: RainfallEventOut[]
  runs: RunoffRunOut[]
  comparison: ScenarioComparisonOut | null
  busy: boolean
  onCreateManualEvent: (payload: RainfallEventManualIn) => void
  onLoadGaugeEvent: () => void
  onImportCsvEvent: (file: File, name: string, sourceType: string) => void
  onRunRunoff: (payload: RunoffRunIn) => void
  onActivateRun: (runId: string) => void
  onRun2DSolver: (runId: string) => void
  onCompare: (runA: string, runB: string) => void
}

const COVER_OPTIONS = [
  {
    code: 'soja_maiz_sd_buena',
    label: 'Soja / Maíz en Siembra Directa con rastrojo (>30%)',
  },
  {
    code: 'soja_maiz_convencional',
    label: 'Cultivo anual en hilera con baja cobertura / labranza',
  },
  {
    code: 'trigo_cereal_invierno_sd',
    label: 'Trigo / Cereal de invierno denso en Siembra Directa',
  },
  {
    code: 'cultivo_cobertura_vicia_centeno',
    label: 'Cultivo de servicio / cobertura densa (Vicia / Centeno)',
  },
  {
    code: 'pastura_pradera_buena',
    label: 'Pastura consociada / verdeo en buena condición',
  },
  {
    code: 'pastura_sobrepastoreada',
    label: 'Pastizal / campo natural con pastoreo intenso',
  },
  {
    code: 'barbecho_con_rastrojo',
    label: 'Barbecho químico con rastrojo conservado',
  },
  {
    code: 'barbecho_suelo_desnudo',
    label: 'Barbecho descubierto / suelo desnudo',
  },
]

export function RainfallRunoffPanel({
  hasTerrain,
  events,
  runs,
  comparison,
  busy,
  onCreateManualEvent,
  onLoadGaugeEvent,
  onImportCsvEvent,
  onRunRunoff,
  onActivateRun,
  onRun2DSolver,
  onCompare,
}: Props) {
  const [rainName, setRainName] = useState<string>('Tormenta diseño 60 mm')
  const [rainMm, setRainMm] = useState<number>(60)
  const [rainSource, setRainSource] = useState<RainfallSourceType>('manual')

  const [selectedEventId, setSelectedEventId] = useState<string>('')
  const [scenarioName, setScenarioName] = useState<string>('')
  const [soilGroup, setSoilGroup] = useState<SoilGroup>('B')
  const [coverCode, setCoverCode] = useState<string>('soja_maiz_sd_buena')
  const [coverPct, setCoverPct] = useState<number>(60)
  const [compaction, setCompaction] = useState<boolean>(false)
  const [amc, setAmc] = useState<AntecedentMoisture>('medium')
  const [lambdaRatio, setLambdaRatio] = useState<number>(0.2)

  const [compareA, setCompareA] = useState<string>('')
  const [compareB, setCompareB] = useState<string>('')

  const effectiveEventId = selectedEventId || events[0]?.id || ''
  const activeEvent = events.find((e) => e.id === effectiveEventId) ?? null
  const activeRun = runs.find((r) => r.is_active) ?? runs[0] ?? null

  const handleAddManual = () => {
    if (!rainName.trim() || rainMm <= 0) return
    onCreateManualEvent({
      name: rainName.trim(),
      total_mm: rainMm,
      source_type: rainSource,
    })
  }

  const handleCsvChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    onImportCsvEvent(
      file,
      file.name.replace(/\.csv$/i, ''),
      rainSource === 'manual' ? 'gauge' : rainSource,
    )
  }

  const handleExecuteRun = () => {
    if (!effectiveEventId) return
    onRunRunoff({
      name: scenarioName.trim() || null,
      rainfall_event_id: effectiveEventId,
      soil_group: soilGroup,
      cover_code: coverCode,
      cover_percent: coverPct,
      compaction_high: compaction,
      antecedent_moisture: amc,
      lambda_ratio: lambdaRatio,
    })
    setScenarioName('')
  }

  const effCompareA = compareA || runs[1]?.id || runs[0]?.id || ''
  const effCompareB = compareB || runs[0]?.id || ''

  return (
    <div className="stack">
      <section className="card">
        <h3>4. Evento de lluvia (Fase 2 · Manual o CSV)</h3>
        <div className="btn-row">
          <button
            className="btn-primary"
            onClick={onLoadGaugeEvent}
            disabled={!hasTerrain || busy}
          >
            Tormenta CSV 80 mm (Pluviómetro)
          </button>
          <label className="btn-secondary">
            Importar CSV temporal
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={handleCsvChange}
              disabled={!hasTerrain || busy}
              hidden
            />
          </label>
        </div>

        <div className="two-cols">
          <label className="field-label">
            Nombre del evento manual
            <input
              type="text"
              value={rainName}
              onChange={(e) => setRainName(e.target.value)}
            />
          </label>
          <label className="field-label">
            Lluvia total P (mm)
            <input
              type="number"
              min={1}
              max={1000}
              step={5}
              value={rainMm}
              onChange={(e) => setRainMm(Number(e.target.value))}
            />
          </label>
        </div>

        <div className="two-cols">
          <label className="field-label">
            Fuente del dato (SDD §5.3)
            <select
              value={rainSource}
              onChange={(e) =>
                setRainSource(e.target.value as RainfallSourceType)
              }
            >
              <option value="gauge">Pluviómetro del establecimiento</option>
              <option value="NASA_POWER">NASA POWER (MERRA-2 / GPCP · ~55 km)</option>
              <option value="IMERG">NASA GPM IMERG (0,1° · 30 min)</option>
              <option value="CHIRPS">CHIRPS v3 (0,05° · diario)</option>
              <option value="ERA5-Land">Copernicus ERA5-Land (0,1°)</option>
              <option value="SMN">Estación SMN (referencia de estación / manual)</option>
              <option value="manual">Escenario manual exploratorio</option>
            </select>
          </label>
          <div className="field-label" style={{ justifyContent: 'flex-end' }}>
            <button
              className="btn-secondary"
              onClick={handleAddManual}
              disabled={!hasTerrain || busy}
            >
              + Agregar lluvia manual
            </button>
          </div>
        </div>

        {events.length > 0 && (
          <label className="field-label">
            Evento de lluvia seleccionado ({events.length} cargados)
            <select
              value={effectiveEventId}
              onChange={(e) => setSelectedEventId(e.target.value)}
            >
              {events.map((ev) => (
                <option key={ev.id} value={ev.id}>
                  {ev.name} · {ev.total_mm.toFixed(1)} mm (
                  {ev.has_time_series
                    ? `CSV ${ev.interval_minutes} min`
                    : 'Acumulado'}
                  )
                </option>
              ))}
            </select>
          </label>
        )}

        {activeEvent && (
          <div className="rain-meta">
            <dl className="kv-grid">
              <div>
                <dt>Fuente / producto</dt>
                <dd>{String(activeEvent.source_metadata.source ?? activeEvent.source_type)}</dd>
              </div>
              <div>
                <dt>Res. espacial / temp.</dt>
                <dd>
                  {String(activeEvent.source_metadata.spatial_resolution)} ·{' '}
                  {activeEvent.has_time_series
                    ? `${activeEvent.interval_minutes} min`
                    : 'Acumulado'}
                </dd>
              </div>
              {activeEvent.max_intensity_mm_h !== null && (
                <div>
                  <dt>Intensidad máx. serie</dt>
                  <dd>{activeEvent.max_intensity_mm_h.toFixed(1)} mm/h</dd>
                </div>
              )}
            </dl>
            {activeEvent.warnings.map((w, i) => (
              <div key={i} className="alert alert-advertencia">
                {w}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h3>5. Escorrentía NRCS Curve Number (CN) + MFD</h3>
        <div className="two-cols">
          <label className="field-label">
            Grupo hidrológico suelo
            <select
              value={soilGroup}
              onChange={(e) => setSoilGroup(e.target.value as SoilGroup)}
            >
              <option value="A">Grupo A (alta infiltración)</option>
              <option value="B">Grupo B (franco / moderada)</option>
              <option value="C">Grupo C (franco-arcilloso / lenta)</option>
              <option value="D">Grupo D (arcilloso / muy baja)</option>
            </select>
          </label>
          <label className="field-label">
            Humedad antecedente (AMC)
            <select
              value={amc}
              onChange={(e) => setAmc(e.target.value as AntecedentMoisture)}
            >
              <option value="dry">AMC I — Seca</option>
              <option value="medium">AMC II — Media / Normal</option>
              <option value="wet">AMC III — Húmeda</option>
            </select>
          </label>
        </div>

        <label className="field-label">
          Uso / cobertura y manejo del lote
          <select
            value={coverCode}
            onChange={(e) => setCoverCode(e.target.value)}
          >
            {COVER_OPTIONS.map((c) => (
              <option key={c.code} value={c.code}>
                {c.label}
              </option>
            ))}
          </select>
        </label>

        <div className="two-cols">
          <label className="field-label">
            Cobertura suelo (%)
            <input
              type="number"
              min={0}
              max={100}
              step={5}
              value={coverPct}
              onChange={(e) => setCoverPct(Number(e.target.value))}
            />
          </label>
          <label className="field-label">
            Coef. abstracción λ (Ia/S)
            <input
              type="number"
              min={0.05}
              max={0.4}
              step={0.05}
              value={lambdaRatio}
              onChange={(e) => setLambdaRatio(Number(e.target.value))}
            />
          </label>
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={compaction}
            onChange={(e) => setCompaction(e.target.checked)}
          />
          <span>Compactación superficial / huellas de tránsito (+3 CN)</span>
        </label>

        <label className="field-label">
          Nombre del escenario (opcional)
          <input
            type="text"
            placeholder="Ej. 80 mm · Suelo B húmedo · SD"
            value={scenarioName}
            onChange={(e) => setScenarioName(e.target.value)}
          />
        </label>

        <button
          className="btn-primary full-width"
          onClick={handleExecuteRun}
          disabled={!hasTerrain || !effectiveEventId || busy}
        >
          Calcular escorrentía NRCS-CN y mapa 3D
        </button>

        {activeRun && (
          <div className="hydro-summary">
            <label className="field-label">
              Escenario activo en escena 3D ({runs.length} guardados)
              <select
                value={activeRun.id}
                onChange={(e) => onActivateRun(e.target.value)}
              >
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} → Q = {r.cn_result.runoff_q_mm.toFixed(1)} mm
                  </option>
                ))}
              </select>
            </label>

            <dl className="kv-grid">
              <div>
                <dt>CN_II base → CN ef.</dt>
                <dd>
                  {activeRun.cn_result.cn_ii_base.toFixed(0)} →{' '}
                  {activeRun.cn_result.cn_effective.toFixed(1)}
                </dd>
              </div>
              <div>
                <dt>Retención S / Ia</dt>
                <dd>
                  S {activeRun.cn_result.potential_retention_s_mm.toFixed(1)} ·
                  Ia {activeRun.cn_result.initial_abstraction_ia_mm.toFixed(1)}{' '}
                  mm
                </dd>
              </div>
              <div>
                <dt>Escorrentía directa Q</dt>
                <dd>
                  {activeRun.cn_result.runoff_q_mm.toFixed(2)} mm (
                  {(activeRun.cn_result.runoff_coefficient * 100).toFixed(1)} %)
                </dd>
              </div>
              <div>
                <dt>Pérdidas (Ia + F)</dt>
                <dd>
                  {activeRun.cn_result.total_retention_losses_mm.toFixed(2)} mm
                </dd>
              </div>
              <div>
                <dt>Volumen generado lote</dt>
                <dd>
                  {activeRun.spatial_summary.field_runoff_generated_m3.toFixed(
                    0,
                  )}{' '}
                  m³
                </dd>
              </div>
              <div>
                <dt>Salida neta potencial</dt>
                <dd>
                  {activeRun.spatial_summary.net_outflow_potential_m3.toFixed(
                    0,
                  )}{' '}
                  m³
                </dd>
              </div>
            </dl>
            <div className="alert alert-info">
              <strong>Nota técnica SDD §6.4:</strong> Q (
              {activeRun.cn_result.runoff_q_mm.toFixed(1)} mm) es lámina de
              escorrentía directa del evento; no debe interpretarse como
              profundidad física de inundación.
            </div>

            <button
              className="btn-secondary full-width"
              style={{ marginTop: 8 }}
              onClick={() => onRun2DSolver(activeRun.id)}
              disabled={busy}
            >
              {activeRun.hydrodynamic_2d_summary
                ? '↻ Recalcular Solver Hidrodinámico 2D (Manning · Fase 4)'
                : 'Ejecutar Solver Hidrodinámico 2D (water_depth_m + velocity_m_s · Fase 4)'}
            </button>

            {activeRun.hydrodynamic_2d_summary && (
              <dl className="kv-grid" style={{ marginTop: 8 }}>
                <div>
                  <dt>Prof. máx. 2D (h_max)</dt>
                  <dd>
                    {activeRun.hydrodynamic_2d_summary.max_water_depth_in_field_m.toFixed(
                      3,
                    )}{' '}
                    m
                  </dd>
                </div>
                <div>
                  <dt>Velocidad máx. 2D</dt>
                  <dd>
                    {activeRun.hydrodynamic_2d_summary.max_velocity_in_field_m_s.toFixed(
                      2,
                    )}{' '}
                    m/s (n={activeRun.hydrodynamic_2d_summary.manning_n})
                  </dd>
                </div>
                <div>
                  <dt>Área anegada (≥5 cm)</dt>
                  <dd>
                    {activeRun.hydrodynamic_2d_summary.ponded_area_in_field_ha.toFixed(
                      2,
                    )}{' '}
                    ha (
                    {activeRun.hydrodynamic_2d_summary.ponded_area_in_field_pct.toFixed(
                      1,
                    )}{' '}
                    %)
                  </dd>
                </div>
                <div>
                  <dt>Error balance 2D</dt>
                  <dd>
                    {(
                      activeRun.hydrodynamic_2d_summary
                        .mass_balance_relative_error * 100
                    ).toFixed(4)}{' '}
                    %
                  </dd>
                </div>
              </dl>
            )}
          </div>
        )}
      </section>

      {runs.length >= 2 && (
        <section className="card">
          <h3>6. Comparación de escenarios (CU-04)</h3>
          <div className="two-cols">
            <label className="field-label">
              Escenario Base (A)
              <select
                value={effCompareA}
                onChange={(e) => setCompareA(e.target.value)}
              >
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              Escenario Comparado (B)
              <select
                value={effCompareB}
                onChange={(e) => setCompareB(e.target.value)}
              >
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <button
            className="btn-secondary full-width"
            onClick={() => onCompare(effCompareA, effCompareB)}
            disabled={busy || effCompareA === effCompareB}
          >
            Comparar Escenario B vs. Escenario A
          </button>

          {comparison && (
            <dl className="kv-grid" style={{ marginTop: 10 }}>
              <div>
                <dt>Δ Precipitación</dt>
                <dd>
                  {comparison.delta_precipitation_mm >= 0 ? '+' : ''}
                  {comparison.delta_precipitation_mm.toFixed(1)} mm
                </dd>
              </div>
              <div>
                <dt>Δ CN efectivo</dt>
                <dd>
                  {comparison.delta_cn_effective >= 0 ? '+' : ''}
                  {comparison.delta_cn_effective.toFixed(1)}
                </dd>
              </div>
              <div>
                <dt>Δ Escorrentía Q</dt>
                <dd>
                  {comparison.delta_runoff_q_mm >= 0 ? '+' : ''}
                  {comparison.delta_runoff_q_mm.toFixed(2)} mm
                  {comparison.delta_runoff_q_pct !== null
                    ? ` (${comparison.delta_runoff_q_pct >= 0 ? '+' : ''}${comparison.delta_runoff_q_pct.toFixed(1)} %)`
                    : ''}
                </dd>
              </div>
              <div>
                <dt>Δ Volumen lote</dt>
                <dd>
                  {comparison.delta_field_runoff_generated_m3 >= 0 ? '+' : ''}
                  {comparison.delta_field_runoff_generated_m3.toFixed(0)} m³
                </dd>
              </div>
              <div>
                <dt>Δ Salida neta</dt>
                <dd>
                  {comparison.delta_net_outflow_potential_m3 >= 0 ? '+' : ''}
                  {comparison.delta_net_outflow_potential_m3.toFixed(0)} m³
                </dd>
              </div>
              <div>
                <dt>Δ Zonas alta conc.</dt>
                <dd>
                  {comparison.delta_high_concentration_area_ha >= 0 ? '+' : ''}
                  {comparison.delta_high_concentration_area_ha.toFixed(2)} ha
                </dd>
              </div>
            </dl>
          )}
        </section>
      )}
    </div>
  )
}
