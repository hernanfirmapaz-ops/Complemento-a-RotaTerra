import { useState } from 'react'
import type {
  AgronomicToolkitIn,
  AgronomicToolkitOut,
  SoilGroup,
} from '../types/api'

interface Props {
  hasTerrain: boolean
  toolkit: AgronomicToolkitOut | null
  busy: boolean
  onRun: (params: AgronomicToolkitIn) => void
  onSelect3DLayer: (layer: 'erosion' | 'ndvi') => void
}

export function AgronomicToolkitPanel({
  hasTerrain,
  toolkit,
  busy,
  onRun,
  onSelect3DLayer,
}: Props) {
  const [soilGroup, setSoilGroup] = useState<SoilGroup>('B')
  const [coverCode, setCoverCode] = useState<string>('soja_maiz_sd_buena')
  const [stormMm, setStormMm] = useState<number>(80)
  const [cropCode, setCropCode] = useState<string>('maiz_temprano')
  const [envZone, setEnvZone] = useState<'loma' | 'media_loma' | 'bajo'>(
    'media_loma',
  )
  const [activeTab, setActiveTab] = useState<
    | 'erosion'
    | 'balance'
    | 'anegamiento'
    | 'terrazas'
    | 'siembra'
    | 'rotaciones'
    | 'ndvi'
    | 'heladas'
  >('erosion')

  const handleRun = () => {
    onRun({
      soil_group: soilGroup,
      cover_code: coverCode,
      storm_precipitation_mm: stormMm,
      crop_code: cropCode,
      environment_zone: envZone,
    })
  }

  return (
    <section className="card">
      <h3>
        Suite Complementaria RotaTerra (8 Herramientas Agro-Hidrológicas)
      </h3>

      <div className="two-cols">
        <label className="field-label">
          Cultivo a sembrar (INTA)
          <select
            value={cropCode}
            onChange={(e) => setCropCode(e.target.value)}
          >
            <option value="maiz_temprano">Maíz Temprano</option>
            <option value="maiz_tardio">Maíz Tardío / 2ª</option>
            <option value="soja_primera">Soja de 1ª</option>
            <option value="trigo">Trigo pan</option>
            <option value="girasol">Girasol</option>
            <option value="sorgo_granifero">Sorgo Granífero</option>
            <option value="vicia_centeno_cobertura">
              Vicia + Centeno (Servicio)
            </option>
          </select>
        </label>
        <label className="field-label">
          Ambiente objetivo
          <select
            value={envZone}
            onChange={(e) =>
              setEnvZone(e.target.value as 'loma' | 'media_loma' | 'bajo')
            }
          >
            <option value="loma">Loma bien drenada</option>
            <option value="media_loma">Media loma</option>
            <option value="bajo">Bajo receptor</option>
          </select>
        </label>
      </div>

      <div className="two-cols">
        <label className="field-label">
          Grupo suelo / Tormenta (mm)
          <div style={{ display: 'flex', gap: 6 }}>
            <select
              value={soilGroup}
              onChange={(e) => setSoilGroup(e.target.value as SoilGroup)}
            >
              <option value="A">Suelo A</option>
              <option value="B">Suelo B</option>
              <option value="C">Suelo C</option>
              <option value="D">Suelo D</option>
            </select>
            <input
              type="number"
              min={15}
              max={400}
              step={5}
              value={stormMm}
              onChange={(e) => setStormMm(Number(e.target.value))}
              style={{ width: 70 }}
            />
          </div>
        </label>
        <label className="field-label">
          Manejo actual (USLE C)
          <select
            value={coverCode}
            onChange={(e) => setCoverCode(e.target.value)}
          >
            <option value="soja_maiz_sd_buena">Siembra Directa (&gt;30%)</option>
            <option value="soja_maiz_convencional">Labranza / Baja cob.</option>
            <option value="trigo_cereal_invierno_sd">Cereal invierno SD</option>
            <option value="cultivo_cobertura_vicia_centeno">
              Cobertura Vicia/Centeno
            </option>
            <option value="barbecho_suelo_desnudo">Suelo desnudo</option>
          </select>
        </label>
      </div>

      <button
        className="btn-primary full-width"
        onClick={handleRun}
        disabled={!hasTerrain || busy}
      >
        {toolkit
          ? 'Actualizar 8 herramientas (USLE, NASA POWER, INTA, NDVI)'
          : 'Ejecutar 8 herramientas complementarias RotaTerra'}
      </button>

      {toolkit && (
        <div className="hydro-summary">
          <div className="toolkit-tabs">
            {(
              [
                ['erosion', '1. Erosión USLE'],
                ['balance', '2. Balance Hídrico'],
                ['anegamiento', '3. Aneg. Fecha Real'],
                ['terrazas', '4. Terrazas Nivel'],
                ['siembra', '5. Siembra INTA'],
                ['rotaciones', '6. Rotaciones 3a'],
                ['ndvi', '7. Vigor NDVI'],
                ['heladas', '8. Heladas'],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                className={activeTab === k ? 'tab-btn active' : 'tab-btn'}
                onClick={() => setActiveTab(k)}
              >
                {label}
              </button>
            ))}
          </div>

          {activeTab === 'erosion' && (
            <div>
              <dl className="kv-grid">
                <div>
                  <dt>Pérdida media tormenta</dt>
                  <dd>
                    {toolkit.erosion_usle.mean_soil_loss_t_ha.toFixed(2)} t/ha (
                    {toolkit.erosion_usle.erosion_severity.toUpperCase()})
                  </dd>
                </div>
                <div>
                  <dt>Pérdida total lote</dt>
                  <dd>
                    {toolkit.erosion_usle.total_field_soil_loss_tons.toFixed(1)}{' '}
                    t
                  </dd>
                </div>
                <div>
                  <dt>Factor topográfico LS</dt>
                  <dd>
                    medio {toolkit.erosion_usle.ls_mean_in_field.toFixed(2)} ·
                    máx {toolkit.erosion_usle.ls_max_in_field.toFixed(2)}
                  </dd>
                </div>
                <div>
                  <dt>Focos de cárcavas</dt>
                  <dd>
                    {toolkit.erosion_usle.gully_initiation_cells} celdas (
                    {toolkit.erosion_usle.gully_risk_area_ha.toFixed(2)} ha)
                  </dd>
                </div>
              </dl>
              <button
                className="btn-secondary full-width"
                style={{ marginTop: 8 }}
                onClick={() => onSelect3DLayer('erosion')}
              >
                Ver mapa 3D de Erosión USLE (t/ha)
              </button>
            </div>
          )}

          {activeTab === 'balance' && (
            <div>
              <dl className="kv-grid">
                <div>
                  <dt>Lluvia / ET0 anual</dt>
                  <dd>
                    {toolkit.water_balance_monthly.annual_precipitation_mm.toFixed(
                      0,
                    )}{' '}
                    / {toolkit.water_balance_monthly.annual_et0_mm.toFixed(0)}{' '}
                    mm
                  </dd>
                </div>
                <div>
                  <dt>Agua útil actual</dt>
                  <dd>
                    {toolkit.water_balance_monthly.final_available_water_mm.toFixed(
                      0,
                    )}{' '}
                    mm (
                    {toolkit.water_balance_monthly.final_available_water_pct.toFixed(
                      0,
                    )}{' '}
                    %)
                  </dd>
                </div>
                <div>
                  <dt>Meses con déficit</dt>
                  <dd>
                    {toolkit.water_balance_monthly.deficit_months_count} de 12
                  </dd>
                </div>
                <div>
                  <dt>Meses con exceso</dt>
                  <dd>
                    {toolkit.water_balance_monthly.excess_months_count} de 12
                  </dd>
                </div>
              </dl>
              <div className="mini-table-wrap">
                <table className="mini-table">
                  <thead>
                    <tr>
                      <th>Mes</th>
                      <th>P (mm)</th>
                      <th>ET0</th>
                      <th>Agua útil</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {toolkit.water_balance_monthly.months
                      .slice(-6)
                      .map((m) => (
                        <tr key={m.label}>
                          <td>{m.label}</td>
                          <td>{m.precipitation_mm.toFixed(0)}</td>
                          <td>{m.et0_mm.toFixed(0)}</td>
                          <td>{m.available_water_pct.toFixed(0)} %</td>
                          <td>{m.status}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'anegamiento' && (
            <div>
              <dl className="kv-grid">
                <div>
                  <dt>Tormentas reales eval.</dt>
                  <dd>
                    {toolkit.real_waterlogging_by_date.significant_storms_count}{' '}
                    eventos
                  </dd>
                </div>
                <div>
                  <dt>Eventos riesgo ALTO</dt>
                  <dd>
                    {
                      toolkit.real_waterlogging_by_date
                        .high_waterlogging_events_count
                    }{' '}
                    fechas
                  </dd>
                </div>
              </dl>
              <div className="mini-table-wrap">
                <table className="mini-table">
                  <thead>
                    <tr>
                      <th>Fecha real</th>
                      <th>P</th>
                      <th>5d prev</th>
                      <th>Q</th>
                      <th>Riesgo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {toolkit.real_waterlogging_by_date.top_historical_events
                      .slice(0, 5)
                      .map((ev) => (
                        <tr key={ev.date}>
                          <td>{ev.date}</td>
                          <td>{ev.precipitation_mm.toFixed(0)} mm</td>
                          <td>
                            {ev.prior_5d_rain_mm.toFixed(0)} ({ev.antecedent_moisture_amc})
                          </td>
                          <td>{ev.runoff_q_mm.toFixed(1)} mm</td>
                          <td>{ev.waterlogging_risk.toUpperCase()}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'terrazas' && (
            <dl className="kv-grid">
              <div>
                <dt>Intervalo vert. / horiz.</dt>
                <dd>
                  VI {toolkit.contour_terraces.recommended_vertical_interval_m}{' '}
                  m · HI{' '}
                  {toolkit.contour_terraces.recommended_horizontal_spacing_m} m
                </dd>
              </div>
              <div>
                <dt>Terrazas trazadas</dt>
                <dd>
                  {toolkit.contour_terraces.terrace_levels_count} curvas (
                  {toolkit.contour_terraces.estimated_total_terrace_length_m.toFixed(
                    0,
                  )}{' '}
                  m)
                </dd>
              </div>
              <div>
                <dt>Agua frenada terrazas</dt>
                <dd>
                  {toolkit.contour_terraces.water_retained_by_terraces_m3.toFixed(
                    0,
                  )}{' '}
                  m³ (-{toolkit.contour_terraces.runoff_reduction_pct.toFixed(1)}{' '}
                  % Q)
                </dd>
              </div>
              <div>
                <dt>Erosión antes → después</dt>
                <dd>
                  {toolkit.contour_terraces.soil_loss_before_t_ha.toFixed(2)} →{' '}
                  {toolkit.contour_terraces.soil_loss_after_t_ha.toFixed(2)}{' '}
                  t/ha (-
                  {toolkit.contour_terraces.erosion_reduction_pct.toFixed(1)} %)
                </dd>
              </div>
            </dl>
          )}

          {activeTab === 'siembra' && (
            <dl className="kv-grid">
              <div>
                <dt>Cultivo / Ventana INTA</dt>
                <dd>{toolkit.seeding_calculator_inta.crop_label}</dd>
              </div>
              <div>
                <dt>Fecha recomendada</dt>
                <dd>{toolkit.seeding_calculator_inta.sowing_window_inta}</dd>
              </div>
              <div>
                <dt>Densidad objetivo</dt>
                <dd>
                  {toolkit.seeding_calculator_inta.target_plants_ha.toLocaleString()}{' '}
                  pl/ha (
                  {toolkit.seeding_calculator_inta.seeds_per_linear_m.toFixed(1)}{' '}
                  sem/m)
                </dd>
              </div>
              <div>
                <dt>Semilla requerida</dt>
                <dd>
                  {toolkit.seeding_calculator_inta.seed_density_kg_ha.toFixed(1)}{' '}
                  kg/ha (
                  {toolkit.seeding_calculator_inta.commercial_bags_needed.toFixed(
                    1,
                  )}{' '}
                  bolsas lote)
                </dd>
              </div>
              <div>
                <dt>Nutrientes (N - P2O5 - S)</dt>
                <dd>
                  {toolkit.seeding_calculator_inta.nutrients_required_kg_ha.N} -{' '}
                  {
                    toolkit.seeding_calculator_inta.nutrients_required_kg_ha
                      .P2O5_equiv
                  }{' '}
                  - {toolkit.seeding_calculator_inta.nutrients_required_kg_ha.S}{' '}
                  kg/ha
                </dd>
              </div>
              <div>
                <dt>Guía MAP / Urea / Yeso</dt>
                <dd>
                  MAP{' '}
                  {toolkit.seeding_calculator_inta.commercial_fertilizer_guide_kg_ha.MAP_11_52_0_kg_ha.toFixed(
                    0,
                  )}{' '}
                  · Urea{' '}
                  {toolkit.seeding_calculator_inta.commercial_fertilizer_guide_kg_ha.Urea_46_0_0_kg_ha.toFixed(
                    0,
                  )}{' '}
                  kg/ha
                </dd>
              </div>
            </dl>
          )}

          {activeTab === 'rotaciones' && (
            <dl className="kv-grid">
              <div>
                <dt>Escorrentía 3a (A vs B)</dt>
                <dd>
                  {toolkit.rotation_comparator_3yr.sequence_a.cumulative_runoff_3yr_mm.toFixed(
                    0,
                  )}{' '}
                  vs.{' '}
                  {toolkit.rotation_comparator_3yr.sequence_b.cumulative_runoff_3yr_mm.toFixed(
                    0,
                  )}{' '}
                  mm
                </dd>
              </div>
              <div>
                <dt>Erosión 3a (A vs B)</dt>
                <dd>
                  {toolkit.rotation_comparator_3yr.sequence_a.cumulative_soil_loss_3yr_t_ha.toFixed(
                    2,
                  )}{' '}
                  vs.{' '}
                  {toolkit.rotation_comparator_3yr.sequence_b.cumulative_soil_loss_3yr_t_ha.toFixed(
                    2,
                  )}{' '}
                  t/ha
                </dd>
              </div>
              <div>
                <dt>Suelo ahorrado en 3 años</dt>
                <dd>
                  {toolkit.rotation_comparator_3yr.delta_b_vs_a.soil_saved_by_b_tons.toFixed(
                    1,
                  )}{' '}
                  toneladas en el lote
                </dd>
              </div>
              <div>
                <dt>Ganancia cobertura media</dt>
                <dd>
                  +
                  {toolkit.rotation_comparator_3yr.delta_b_vs_a.cover_gain_pct.toFixed(
                    0,
                  )}{' '}
                  % cobertura
                </dd>
              </div>
            </dl>
          )}

          {activeTab === 'ndvi' && (
            <div>
              <dl className="kv-grid">
                <div>
                  <dt>Fuente NDVI</dt>
                  <dd>{toolkit.ndvi_vigor_monitor.source.slice(0, 38)}</dd>
                </div>
                <div>
                  <dt>NDVI medio lote</dt>
                  <dd>
                    {toolkit.ndvi_vigor_monitor.mean_ndvi_in_field.toFixed(3)}
                  </dd>
                </div>
                <div>
                  <dt>Zonas débiles (&lt;0,38)</dt>
                  <dd>
                    {toolkit.ndvi_vigor_monitor.low_vigor_area_ha.toFixed(1)} ha
                    ({toolkit.ndvi_vigor_monitor.low_vigor_pct.toFixed(1)} %)
                  </dd>
                </div>
                <div>
                  <dt>Coincidencia con bajos/vías</dt>
                  <dd>
                    {toolkit.ndvi_vigor_monitor.weak_zones_explained_by_waterlogging_or_erosion_pct.toFixed(
                      1,
                    )}{' '}
                    % explicado por relieve
                  </dd>
                </div>
              </dl>
              <button
                className="btn-secondary full-width"
                style={{ marginTop: 8 }}
                onClick={() => onSelect3DLayer('ndvi')}
              >
                Ver mapa 3D de Vigor Vegetativo (NDVI)
              </button>
            </div>
          )}

          {activeTab === 'heladas' && (
            <div>
              <dl className="kv-grid">
                <div>
                  <dt>Última helada primavera</dt>
                  <dd>
                    {toolkit.frost_risk_sowing.median_last_spring_frost_date}
                  </dd>
                </div>
                <div>
                  <dt>Siembra segura (P90)</dt>
                  <dd>
                    desde{' '}
                    {toolkit.frost_risk_sowing.safe_spring_sowing_start_date}
                  </dd>
                </div>
                <div>
                  <dt>Primera helada otoño</dt>
                  <dd>
                    {toolkit.frost_risk_sowing.median_first_autumn_frost_date}
                  </dd>
                </div>
                <div>
                  <dt>Ventana libre heladas</dt>
                  <dd>{toolkit.frost_risk_sowing.frost_free_period_days} días</dd>
                </div>
              </dl>
              <ul className="limitations-list" style={{ marginTop: 8 }}>
                {toolkit.frost_risk_sowing.safe_sowing_windows_by_crop.map(
                  (w) => (
                    <li key={w.crop}>
                      <strong>{w.crop}</strong> (desde {w.safe_start}): {w.note}
                    </li>
                  ),
                )}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
