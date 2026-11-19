import type { FieldOut, MeshOut, TerrainOut } from '../types/api'

interface Props {
  field: FieldOut
  terrain: TerrainOut | null
  mesh: MeshOut | null
}

export function QualityPanel({ field, terrain, mesh }: Props) {
  return (
    <div className="stack">
      <div className="card">
        <h4>Propiedades del lote</h4>
        <dl className="kv-grid">
          <div>
            <dt>Nombre</dt>
            <dd>{field.name}</dd>
          </div>
          <div>
            <dt>Superficie UTM</dt>
            <dd>{field.area_ha.toFixed(2)} ha</dd>
          </div>
          {field.declared_area_ha !== null && (
            <div>
              <dt>Sup. declarada</dt>
              <dd>{field.declared_area_ha.toFixed(2)} ha</dd>
            </div>
          )}
          <div>
            <dt>CRS métrico</dt>
            <dd>EPSG:{field.utm_epsg}</dd>
          </div>
          <div>
            <dt>Centroide</dt>
            <dd>
              {field.centroid[1].toFixed(4)}°, {field.centroid[0].toFixed(4)}°
            </dd>
          </div>
        </dl>
        {field.warnings.map((w, i) => (
          <div key={i} className="alert alert-advertencia">
            {w}
          </div>
        ))}
      </div>

      {terrain && (
        <>
          <div className="card">
            <h4>Fuente y calidad del DEM</h4>
            <dl className="kv-grid">
              <div>
                <dt>Fuente</dt>
                <dd>{terrain.source.source_name}</dd>
              </div>
              <div>
                <dt>Tipo superficie</dt>
                <dd>{terrain.source.surface_type}</dd>
              </div>
              <div>
                <dt>Resolución</dt>
                <dd>{terrain.quality.pixel_size_m.toFixed(1)} m/píxel</dd>
              </div>
              <div>
                <dt>Datum vertical</dt>
                <dd>{terrain.source.vertical_datum ?? 'No declarado'}</dd>
              </div>
              <div>
                <dt>Precisión vert.</dt>
                <dd>
                  {terrain.source.vertical_accuracy_m !== null
                    ? `±${terrain.source.vertical_accuracy_m} m`
                    : 'No declarada'}
                </dd>
              </div>
              <div>
                <dt>Adquisición</dt>
                <dd>
                  {terrain.source.acquisition_start
                    ? `${terrain.source.acquisition_start}${
                        terrain.source.acquisition_end &&
                        terrain.source.acquisition_end !==
                          terrain.source.acquisition_start
                          ? ` a ${terrain.source.acquisition_end}`
                          : ''
                      }`
                    : 'No declarada'}
                </dd>
              </div>
              <div>
                <dt>Celdas en lote</dt>
                <dd>{terrain.quality.cells_in_field}</dd>
              </div>
              <div>
                <dt>Zona de aporte</dt>
                <dd>+{terrain.quality.buffer_m.toFixed(0)} m</dd>
              </div>
              <div>
                <dt>Nodata lote</dt>
                <dd>{terrain.quality.nodata_pct_field.toFixed(2)} %</dd>
              </div>
              <div>
                <dt>Cotas en lote</dt>
                <dd>
                  {terrain.quality.elevation_field.min !== null
                    ? `${terrain.quality.elevation_field.min.toFixed(1)} – ${terrain.quality.elevation_field.max?.toFixed(1)} m (Δ ${terrain.quality.elevation_field.range?.toFixed(1)} m)`
                    : 's/d'}
                </dd>
              </div>
              {mesh && (
                <div>
                  <dt>Malla 3D</dt>
                  <dd>
                    {mesh.cols}×{mesh.rows} ({mesh.mesh_cell_size_m.toFixed(1)}{' '}
                    m, factor {mesh.decimation}×)
                  </dd>
                </div>
              )}
            </dl>

            <div className="warnings-list">
              {terrain.quality.warnings.map((w) => (
                <div key={w.code} className={`alert alert-${w.level}`}>
                  <strong>[{w.level.toUpperCase()}]</strong> {w.message}
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h4>Alcance y limitaciones (Fase 0)</h4>
            <ul className="limitations-list">
              {terrain.limitations.map((lim, idx) => (
                <li key={idx}>{lim}</li>
              ))}
            </ul>
            {terrain.source.license && (
              <p className="license-note">{terrain.source.license}</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
