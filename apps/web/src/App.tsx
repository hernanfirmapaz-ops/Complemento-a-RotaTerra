import { useEffect, useState } from 'react'
import {
  computeTerrainProfile,
  getStaticHydrology,
  getTerrain,
  getTerrainMesh,
  importFieldGeoJSON,
  listFields,
  loadSampleField,
  processTerrain,
  queryTerrainPoint,
  runStaticHydrology,
} from './services/api'
import type {
  FieldOut,
  HydrologyOut,
  HydrologyRunIn,
  MeshOut,
  PointOut,
  ProfileOut,
  TerrainOut,
} from './types/api'
import {
  type InteractionMode,
  type LayerVisibility,
  type SurfaceColorMode,
  TerrainScene3D,
} from './components/TerrainScene3D'
import { HydrologyPanel } from './components/HydrologyPanel'
import { ProfileChart } from './components/ProfileChart'
import { QualityPanel } from './components/QualityPanel'

export function App() {
  const [fields, setFields] = useState<FieldOut[]>([])
  const [activeFieldId, setActiveFieldId] = useState<string | null>(null)
  const [terrain, setTerrain] = useState<TerrainOut | null>(null)
  const [mesh, setMesh] = useState<MeshOut | null>(null)
  const [hydrology, setHydrology] = useState<HydrologyOut | null>(null)

  const [sourceId, setSourceId] = useState<'copernicus_glo30' | 'upload'>(
    'copernicus_glo30',
  )
  const [bufferM, setBufferM] = useState<number>(300)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadSurfaceType, setUploadSurfaceType] = useState<
    'DTM' | 'DSM' | 'desconocido'
  >('DTM')
  const [uploadDatum, setUploadDatum] = useState<string>('EGM2008')
  const [uploadAccuracy, setUploadAccuracy] = useState<string>('')

  const [viewMode, setViewMode] = useState<'2d' | '3d'>('3d')
  const [exaggeration, setExaggeration] = useState<number>(1)
  const [layers, setLayers] = useState<LayerVisibility>({
    basemap: 'satellite',
    surfaceColor: 'elevation',
    mesh3d: true,
    wireframe: false,
    boundary: true,
    contours: true,
    drainageNetwork: true,
    depressionsAndOutlets: true,
  })
  const [interactionMode, setInteractionMode] =
    useState<InteractionMode>('inspect')

  const [cursorCoords, setCursorCoords] = useState<[number, number] | null>(
    null,
  )
  const [selectedPoint, setSelectedPoint] = useState<PointOut | null>(null)
  const [profileDraft, setProfileDraft] = useState<[number, number][]>([])
  const [profileResult, setProfileResult] = useState<ProfileOut | null>(null)

  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const activeField = fields.find((f) => f.id === activeFieldId) ?? null

  useEffect(() => {
    listFields()
      .then((list) => {
        setFields(list)
        if (list.length > 0) setActiveFieldId(list[0].id)
      })
      .catch((err: Error) => setError(err.message))
  }, [])

  useEffect(() => {
    setTerrain(null)
    setMesh(null)
    setHydrology(null)
    setSelectedPoint(null)
    setProfileDraft([])
    setProfileResult(null)
    if (!activeField) return
    if (!activeField.has_terrain) return

    setBusy('Cargando terreno y malla 3D...')
    const tasks: Promise<unknown>[] = [
      getTerrain(activeField.id),
      getTerrainMesh(activeField.id),
      activeField.has_hydrology
        ? getStaticHydrology(activeField.id).catch(() => null)
        : Promise.resolve(null),
    ]
    Promise.all(tasks)
      .then(([t, m, h]) => {
        setTerrain(t as TerrainOut)
        setMesh(m as MeshOut)
        setHydrology((h as HydrologyOut | null) ?? null)
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(null))
  }, [activeField?.id, activeField?.has_terrain, activeField?.has_hydrology])

  const handleLoadSample = async () => {
    setError(null)
    setBusy('Importando lote real de muestra (San Luis)...')
    try {
      const imported = await loadSampleField()
      const all = await listFields()
      setFields(all)
      if (imported[0]) setActiveFieldId(imported[0].id)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleImportGeoJSON = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setError(null)
    setBusy(`Validando e importando ${file.name}...`)
    try {
      const imported = await importFieldGeoJSON(file)
      const all = await listFields()
      setFields(all)
      if (imported[0]) setActiveFieldId(imported[0].id)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleProcessTerrain = async () => {
    if (!activeField) return
    setError(null)
    setBusy(
      sourceId === 'copernicus_glo30'
        ? 'Descargando ventana COG Copernicus GLO-30 (30 m) y reproyectando a UTM...'
        : 'Procesando GeoTIFF subido y reproyectando a UTM...',
    )
    try {
      const t = await processTerrain(activeField.id, {
        sourceId,
        bufferM,
        file: sourceId === 'upload' ? uploadFile : null,
        surfaceType: uploadSurfaceType,
        verticalDatum: uploadDatum,
        verticalAccuracyM: uploadAccuracy,
      })
      const m = await getTerrainMesh(activeField.id)
      setTerrain(t)
      setMesh(m)
      setHydrology(null)
      const all = await listFields()
      setFields(all)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleRunHydrology = async (params: HydrologyRunIn) => {
    if (!activeField) return
    setError(null)
    setBusy(
      'Calculando acondicionamiento selectivo, direcciones D8, acumulación MFD, depresiones y red de drenaje...',
    )
    try {
      const h = await runStaticHydrology(activeField.id, params)
      const m = await getTerrainMesh(activeField.id)
      setHydrology(h)
      setMesh(m)
      setLayers((prev) => ({
        ...prev,
        surfaceColor: 'mfd',
        contours: true,
        drainageNetwork: true,
        depressionsAndOutlets: true,
      }))
      const all = await listFields()
      setFields(all)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleMapClick = async (lon: number, lat: number) => {
    if (!activeField || !terrain) return
    setError(null)
    if (interactionMode === 'inspect') {
      try {
        const pt = await queryTerrainPoint(activeField.id, lon, lat)
        setSelectedPoint(pt)
      } catch (err) {
        setError((err as Error).message)
      }
      return
    }

    const next: [number, number][] = [...profileDraft, [lon, lat]]
    setProfileDraft(next)
    if (next.length >= 2) {
      try {
        const pf = await computeTerrainProfile(activeField.id, next)
        setProfileResult(pf)
      } catch (err) {
        setError((err as Error).message)
      }
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="badge-phase">FASE 0 + FASE 1 · HIDROLOGÍA ESTÁTICA</span>
          <h1>RotaTerra — Visor 3D de Lotes y Drenaje Superficial</h1>
        </div>
        <div className="topbar-controls">
          <div className="segmented" role="group" aria-label="Modo de vista">
            <button
              className={viewMode === '2d' ? 'active' : ''}
              onClick={() => setViewMode('2d')}
            >
              Vista 2D
            </button>
            <button
              className={viewMode === '3d' ? 'active' : ''}
              onClick={() => setViewMode('3d')}
            >
              Escena 3D
            </button>
          </div>

          <div
            className="segmented"
            role="group"
            aria-label="Herramienta de clic"
          >
            <button
              className={interactionMode === 'inspect' ? 'active' : ''}
              onClick={() => setInteractionMode('inspect')}
              title="Inspeccionar cota, pendiente y área contribuyente en un punto"
            >
              Inspeccionar punto
            </button>
            <button
              className={interactionMode === 'profile' ? 'active' : ''}
              onClick={() => setInteractionMode('profile')}
              title="Dibujar polilínea en el mapa para perfil altimétrico"
            >
              Trazar perfil ({profileDraft.length} pts)
            </button>
          </div>

          <label className="exag-control">
            <span>Exageración vertical:</span>
            <select
              value={exaggeration}
              onChange={(e) => setExaggeration(Number(e.target.value))}
            >
              <option value={1}>1× (escala real)</option>
              <option value={2}>2× (visual)</option>
              <option value={3}>3× (visual)</option>
              <option value={5}>5× (visual)</option>
            </select>
          </label>
        </div>
      </header>

      <div className="workspace">
        {/* Panel izquierdo: Lotes, fuente de DEM, Hidrología Fase 1 y capas */}
        <aside className="sidebar sidebar-left">
          <section className="card">
            <div className="card-header">
              <h3>1. Lotes agrícolas</h3>
            </div>
            <div className="btn-row">
              <button
                className="btn-primary"
                onClick={handleLoadSample}
                disabled={Boolean(busy)}
              >
                Cargar lote real (San Luis)
              </button>
              <label className="btn-secondary">
                Importar GeoJSON
                <input
                  type="file"
                  accept=".geojson,.json,application/geo+json,application/json"
                  onChange={handleImportGeoJSON}
                  hidden
                />
              </label>
            </div>

            {fields.length > 0 && (
              <label className="field-label">
                Lote activo
                <select
                  value={activeFieldId ?? ''}
                  onChange={(e) => setActiveFieldId(e.target.value)}
                >
                  {fields.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name} ({f.area_ha.toFixed(1)} ha)
                      {f.has_hydrology
                        ? ' · D8/MFD listo'
                        : f.has_terrain
                          ? ' · DEM listo'
                          : ''}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </section>

          <section className="card">
            <h3>2. Modelo Digital de Elevación (MDE)</h3>
            <label className="field-label">
              Fuente de elevación
              <select
                value={sourceId}
                onChange={(e) =>
                  setSourceId(
                    e.target.value as 'copernicus_glo30' | 'upload',
                  )
                }
              >
                <option value="copernicus_glo30">
                  Copernicus DEM GLO-30 (30 m · ESA / AWS COG)
                </option>
                <option value="upload">
                  Subir GeoTIFF propio (Dron / LiDAR / IGN 5 m)
                </option>
              </select>
            </label>

            <label className="field-label">
              Zona de aporte externa (buffer en metros)
              <input
                type="number"
                min={0}
                max={5000}
                step={50}
                value={bufferM}
                onChange={(e) => setBufferM(Number(e.target.value))}
              />
            </label>

            {sourceId === 'upload' && (
              <div className="upload-meta">
                <label className="field-label">
                  Archivo GeoTIFF
                  <input
                    type="file"
                    accept=".tif,.tiff,image/tiff"
                    onChange={(e) =>
                      setUploadFile(e.target.files?.[0] ?? null)
                    }
                  />
                </label>
                <label className="field-label">
                  Tipo de superficie
                  <select
                    value={uploadSurfaceType}
                    onChange={(e) =>
                      setUploadSurfaceType(
                        e.target.value as 'DTM' | 'DSM' | 'desconocido',
                      )
                    }
                  >
                    <option value="DTM">MDT / DTM (terreno desnudo)</option>
                    <option value="DSM">MDS / DSM (superficie)</option>
                    <option value="desconocido">No declarado</option>
                  </select>
                </label>
                <div className="two-cols">
                  <label className="field-label">
                    Datum vertical
                    <input
                      type="text"
                      value={uploadDatum}
                      onChange={(e) => setUploadDatum(e.target.value)}
                      placeholder="EGM2008 / IGN"
                    />
                  </label>
                  <label className="field-label">
                    Precisión ± (m)
                    <input
                      type="number"
                      step="0.05"
                      value={uploadAccuracy}
                      onChange={(e) => setUploadAccuracy(e.target.value)}
                      placeholder="0.15"
                    />
                  </label>
                </div>
              </div>
            )}

            <button
              className="btn-primary full-width"
              onClick={handleProcessTerrain}
              disabled={!activeField || Boolean(busy)}
            >
              {terrain ? 'Reprocesar DEM del lote' : 'Cargar y procesar DEM'}
            </button>
          </section>

          <HydrologyPanel
            hasTerrain={Boolean(terrain)}
            hydrology={hydrology}
            busy={Boolean(busy)}
            onRun={handleRunHydrology}
          />

          <section className="card">
            <h3>4. Capas del visor 2D / 3D</h3>
            <label className="field-label">
              Mapa base
              <select
                value={layers.basemap}
                onChange={(e) =>
                  setLayers({
                    ...layers,
                    basemap: e.target.value as 'satellite' | 'osm',
                  })
                }
              >
                <option value="satellite">Imagen satelital (Esri)</option>
                <option value="osm">OpenStreetMap</option>
              </select>
            </label>

            <label className="field-label">
              Variable en superficie 3D
              <select
                value={layers.surfaceColor}
                onChange={(e) =>
                  setLayers({
                    ...layers,
                    surfaceColor: e.target.value as SurfaceColorMode,
                  })
                }
              >
                <option value="elevation">
                  Elevación (gradiente hipsométrico)
                </option>
                <option value="hillshade">
                  Sombreado de relieve (Hillshade)
                </option>
                <option value="slope">Pendiente local (%)</option>
                <option value="mfd" disabled={!hydrology}>
                  Acumulación de flujo difuso MFD (ha)
                </option>
                <option value="d8" disabled={!hydrology}>
                  Acumulación de flujo concentrado D8 (ha)
                </option>
                <option value="depressions" disabled={!hydrology}>
                  Profundidad de depresiones / bajos (m)
                </option>
                <option value="subbasins" disabled={!hydrology}>
                  Subcuencas por punto de salida
                </option>
              </select>
            </label>

            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={layers.mesh3d}
                onChange={(e) =>
                  setLayers({ ...layers, mesh3d: e.target.checked })
                }
              />
              <span>Superficie 3D del terreno</span>
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={layers.boundary}
                onChange={(e) =>
                  setLayers({ ...layers, boundary: e.target.checked })
                }
              />
              <span>Perímetro del lote (3D + 2D)</span>
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={layers.contours}
                disabled={!hydrology}
                onChange={(e) =>
                  setLayers({ ...layers, contours: e.target.checked })
                }
              />
              <span>Curvas de nivel</span>
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={layers.drainageNetwork}
                disabled={!hydrology}
                onChange={(e) =>
                  setLayers({ ...layers, drainageNetwork: e.target.checked })
                }
              />
              <span>Rutas potenciales de escurrimiento</span>
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={layers.depressionsAndOutlets}
                disabled={!hydrology}
                onChange={(e) =>
                  setLayers({
                    ...layers,
                    depressionsAndOutlets: e.target.checked,
                  })
                }
              />
              <span>Depresiones (magenta) y salidas (cian)</span>
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={layers.wireframe}
                onChange={(e) =>
                  setLayers({ ...layers, wireframe: e.target.checked })
                }
              />
              <span>Malla de alambre (wireframe de celdas)</span>
            </label>
          </section>
        </aside>

        {/* Centro: Escena 2D/3D */}
        <main className="center-stage">
          {busy && <div className="status-toast">{busy}</div>}
          {error && (
            <div className="error-toast" role="alert">
              <span>{error}</span>
              <button onClick={() => setError(null)}>✕</button>
            </div>
          )}
          <TerrainScene3D
            field={activeField}
            mesh={mesh}
            hydrology={hydrology}
            viewMode={viewMode}
            exaggeration={exaggeration}
            layers={layers}
            interactionMode={interactionMode}
            profileDraft={profileDraft}
            selectedPoint={selectedPoint}
            onMapClick={handleMapClick}
            onCursorMove={(lon, lat) => setCursorCoords([lon, lat])}
          />
        </main>

        {/* Panel derecho: Inspector de punto, perfil, salidas/depresiones y calidad del DEM */}
        <aside className="sidebar sidebar-right">
          {selectedPoint && (
            <div className="card">
              <div className="card-header">
                <h4>Inspección de punto</h4>
                <button
                  className="btn-ghost"
                  onClick={() => setSelectedPoint(null)}
                >
                  Cerrar
                </button>
              </div>
              <dl className="kv-grid">
                <div>
                  <dt>Coordenadas</dt>
                  <dd>
                    {selectedPoint.lat.toFixed(5)}°,{' '}
                    {selectedPoint.lon.toFixed(5)}°
                  </dd>
                </div>
                <div>
                  <dt>UTM ({selectedPoint.crs})</dt>
                  <dd>
                    E {selectedPoint.x_utm.toFixed(0)} · N{' '}
                    {selectedPoint.y_utm.toFixed(0)} m
                  </dd>
                </div>
                <div>
                  <dt>Cota interpolada</dt>
                  <dd>
                    {selectedPoint.elevation_m !== null
                      ? `${selectedPoint.elevation_m.toFixed(2)} m s.n.m.`
                      : 'Sin dato'}
                  </dd>
                </div>
                <div>
                  <dt>Pendiente local</dt>
                  <dd>
                    {selectedPoint.slope_pct !== null
                      ? `${selectedPoint.slope_pct.toFixed(2)} % (${selectedPoint.slope_deg?.toFixed(2)}°)`
                      : 's/d (borde)'}
                  </dd>
                </div>
                <div>
                  <dt>Orientación ladera</dt>
                  <dd>
                    {selectedPoint.aspect_deg !== null
                      ? `${selectedPoint.aspect_deg.toFixed(0)}°`
                      : 'Plano / s/d'}
                  </dd>
                </div>
                <div>
                  <dt>Ubicación</dt>
                  <dd>
                    {selectedPoint.inside_field
                      ? 'Dentro del lote'
                      : selectedPoint.inside_dem
                        ? 'Zona de aporte externa'
                        : 'Fuera del DEM'}
                  </dd>
                </div>
                {selectedPoint.d8_direction && (
                  <>
                    <div>
                      <dt>Dirección flujo D8</dt>
                      <dd>
                        {selectedPoint.d8_direction}
                        {selectedPoint.d8_azimuth_deg !== null
                          ? ` (${selectedPoint.d8_azimuth_deg}°)`
                          : ''}
                      </dd>
                    </div>
                    <div>
                      <dt>Área contrib. MFD</dt>
                      <dd>
                        {selectedPoint.mfd_area_ha !== null
                          ? `${selectedPoint.mfd_area_ha.toFixed(3)} ha (${selectedPoint.mfd_area_m2?.toFixed(0)} m²)`
                          : 's/d'}
                      </dd>
                    </div>
                    <div>
                      <dt>Área contrib. D8</dt>
                      <dd>
                        {selectedPoint.d8_area_ha !== null
                          ? `${selectedPoint.d8_area_ha.toFixed(3)} ha (${selectedPoint.d8_area_m2?.toFixed(0)} m²)`
                          : 's/d'}
                      </dd>
                    </div>
                    <div>
                      <dt>Depresión / subcuenca</dt>
                      <dd>
                        {selectedPoint.sink_depth_m &&
                        selectedPoint.sink_depth_m > 0.05
                          ? `Bajo ${selectedPoint.sink_depth_m.toFixed(2)} m`
                          : 'Sin depresión'}{' '}
                        {selectedPoint.subbasin_id
                          ? `· Cuenca #${selectedPoint.subbasin_id}`
                          : ''}
                      </dd>
                    </div>
                  </>
                )}
              </dl>
              {selectedPoint.warnings.map((w, idx) => (
                <div key={idx} className="alert alert-advertencia">
                  {w}
                </div>
              ))}
            </div>
          )}

          {profileResult && (
            <ProfileChart
              profile={profileResult}
              onClear={() => {
                setProfileDraft([])
                setProfileResult(null)
              }}
            />
          )}

          {hydrology && (
            <div className="card">
              <h4>Salidas principales y depresiones del lote</h4>
              {hydrology.outlets.length > 0 && (
                <div className="mini-table-wrap">
                  <span className="subhead">
                    Puntos de salida / concentración (# subcuenca)
                  </span>
                  <table className="mini-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Dir</th>
                        <th>MFD (ha)</th>
                        <th>Aporte ext.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {hydrology.outlets.slice(0, 5).map((o) => (
                        <tr key={o.id}>
                          <td>#{o.id}</td>
                          <td>{o.d8_direction}</td>
                          <td>{o.contributing_area_mfd_ha.toFixed(2)}</td>
                          <td>{o.subbasin_external_inflow_ha.toFixed(2)} ha</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {hydrology.depressions.filter((d) => d.in_field).length > 0 && (
                <div className="mini-table-wrap">
                  <span className="subhead">
                    Depresiones detectadas dentro del lote
                  </span>
                  <table className="mini-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Área</th>
                        <th>Prof. máx</th>
                        <th>Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {hydrology.depressions
                        .filter((d) => d.in_field)
                        .slice(0, 5)
                        .map((d) => (
                          <tr key={d.id}>
                            <td>B{d.id}</td>
                            <td>{d.area_ha.toFixed(2)} ha</td>
                            <td>{d.max_depth_m.toFixed(2)} m</td>
                            <td>
                              {d.filled_in_run ? 'Rellenada' : 'Conservada'}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              )}

              {hydrology.warnings.map((w, idx) => (
                <div key={idx} className="alert alert-advertencia">
                  {w}
                </div>
              ))}
            </div>
          )}

          {activeField ? (
            <QualityPanel
              field={activeField}
              terrain={terrain}
              mesh={mesh}
            />
          ) : (
            <div className="card">
              <h4>Sin lote seleccionado</h4>
              <p className="muted">
                Cargá el lote real de muestra (Parcela Rural 205, San Luis) o
                importá un archivo GeoJSON para iniciar el análisis
                topográfico e hidrológico estático.
              </p>
            </div>
          )}
        </aside>
      </div>

      <footer className="bottombar">
        <span>
          Cursor:{' '}
          {cursorCoords
            ? `${cursorCoords[1].toFixed(5)}°, ${cursorCoords[0].toFixed(5)}°`
            : '—'}
        </span>
        <span>
          Resolución DEM:{' '}
          {terrain ? `${terrain.quality.pixel_size_m.toFixed(1)} m` : '—'}
        </span>
        <span>
          CRS de cálculo:{' '}
          {activeField ? `EPSG:${activeField.utm_epsg} (métrico)` : '—'}
        </span>
        <span>
          Capa 3D: <strong>{layers.surfaceColor.toUpperCase()}</strong>
        </span>
        <span className="phase-note">
          Fase 1: D8 + MFD + depresiones + cuencas (sin lluvia ni lámina
          hidrodinámica)
        </span>
      </footer>
    </div>
  )
}
