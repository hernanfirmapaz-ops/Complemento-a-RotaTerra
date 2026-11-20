/** Cliente HTTP de la API v1 (`/api/v1`). */

import type {
  AgronomicToolkitIn,
  AgronomicToolkitOut,
  CatalogOut,
  ContoursOut,
  DailyRainfallContextOut,
  FieldObservationIn,
  FieldObservationOut,
  FieldOut,
  HealthOut,
  HydrologyOut,
  HydrologyRunIn,
  MeshOut,
  PointOut,
  ProfileOut,
  RainfallEventManualIn,
  RainfallEventOut,
  RunoffRunIn,
  RunoffRunOut,
  RunoffTimelineOut,
  ScenarioComparisonOut,
  SimulateDailyRainIn,
  TerrainOut,
} from '../types/api'

const BASE = '/api/v1'

export async function getHealthCheck(): Promise<HealthOut> {
  const res = await fetch(`${BASE}/health`)
  return check<HealthOut>(res)
}

async function check<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Error HTTP ${res.status}`
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
      else if (Array.isArray(body?.detail))
        detail = body.detail.map((d: { msg?: string }) => d.msg).join('; ')
    } catch {
      // respuesta no JSON
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export async function listFields(): Promise<FieldOut[]> {
  const res = await fetch(`${BASE}/fields`)
  return check<FieldOut[]>(res)
}

export async function loadSampleField(
  preset: 'llanura' | 'serrano' = 'serrano',
): Promise<FieldOut[]> {
  const res = await fetch(`${BASE}/fields/sample?preset=${preset}`, {
    method: 'POST',
  })
  const data = await check<{ fields: FieldOut[] }>(res)
  return data.fields
}

export async function importFieldGeoJSON(
  file: File,
  defaultName?: string,
): Promise<FieldOut[]> {
  const form = new FormData()
  form.append('file', file)
  if (defaultName) form.append('default_name', defaultName)
  const res = await fetch(`${BASE}/fields/import`, {
    method: 'POST',
    body: form,
  })
  const data = await check<{ fields: FieldOut[] }>(res)
  return data.fields
}

export async function getTerrain(fieldId: string): Promise<TerrainOut> {
  const res = await fetch(`${BASE}/fields/${fieldId}/terrain`)
  return check<TerrainOut>(res)
}

export interface ProcessTerrainParams {
  sourceId: 'copernicus_glo30' | 'upload'
  bufferM: number
  file?: File | null
  sourceName?: string
  surfaceType?: 'DTM' | 'DSM' | 'desconocido'
  verticalDatum?: string
  verticalAccuracyM?: string
  acquisitionDate?: string
  acquisitionMethod?: string
}

export async function processTerrain(
  fieldId: string,
  params: ProcessTerrainParams,
): Promise<TerrainOut> {
  const form = new FormData()
  form.append('source_id', params.sourceId)
  form.append('buffer_m', String(params.bufferM))
  if (params.file) form.append('file', params.file)
  if (params.sourceName) form.append('source_name', params.sourceName)
  if (params.surfaceType) form.append('surface_type', params.surfaceType)
  if (params.verticalDatum) form.append('vertical_datum', params.verticalDatum)
  if (params.verticalAccuracyM)
    form.append('vertical_accuracy_m', params.verticalAccuracyM)
  if (params.acquisitionDate)
    form.append('acquisition_date', params.acquisitionDate)
  if (params.acquisitionMethod)
    form.append('acquisition_method', params.acquisitionMethod)

  const res = await fetch(`${BASE}/fields/${fieldId}/terrain/process`, {
    method: 'POST',
    body: form,
  })
  return check<TerrainOut>(res)
}

export async function getTerrainMesh(
  fieldId: string,
  maxSize = 180,
): Promise<MeshOut> {
  const res = await fetch(
    `${BASE}/fields/${fieldId}/terrain/mesh?max_size=${maxSize}`,
  )
  return check<MeshOut>(res)
}

export async function queryTerrainPoint(
  fieldId: string,
  lon: number,
  lat: number,
): Promise<PointOut> {
  const params = new URLSearchParams({
    lon: String(lon),
    lat: String(lat),
  })
  const res = await fetch(`${BASE}/fields/${fieldId}/terrain/point?${params}`)
  return check<PointOut>(res)
}

export async function computeTerrainProfile(
  fieldId: string,
  coordinates: [number, number][],
  step_m?: number | null,
): Promise<ProfileOut> {
  const payload: { coordinates: [number, number][]; step_m?: number } = { coordinates }
  if (step_m != null) payload.step_m = step_m
  const res = await fetch(`${BASE}/fields/${fieldId}/terrain/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return check<ProfileOut>(res)
}

export async function getTerrainContours(
  fieldId: string,
  interval_m: number = 5,
): Promise<ContoursOut> {
  const res = await fetch(`${BASE}/fields/${fieldId}/terrain/contours?interval_m=${interval_m}`)
  return check<ContoursOut>(res)
}

export async function getStaticHydrology(
  fieldId: string,
): Promise<HydrologyOut> {
  const res = await fetch(`${BASE}/fields/${fieldId}/hydrology`)
  return check<HydrologyOut>(res)
}

export async function runStaticHydrology(
  fieldId: string,
  payload: HydrologyRunIn,
): Promise<HydrologyOut> {
  const res = await fetch(`${BASE}/fields/${fieldId}/hydrology/static`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return check<HydrologyOut>(res)
}

export async function listRainfallEvents(
  fieldId: string,
): Promise<RainfallEventOut[]> {
  const res = await fetch(`${BASE}/fields/${fieldId}/hydrology/rainfall-events`)
  return check<RainfallEventOut[]>(res)
}

export async function createManualRainfallEvent(
  fieldId: string,
  payload: RainfallEventManualIn,
): Promise<RainfallEventOut> {
  const res = await fetch(
    `${BASE}/fields/${fieldId}/hydrology/rainfall-events`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
  return check<RainfallEventOut>(res)
}

export async function loadSampleRainfallEvent(
  fieldId: string,
): Promise<RainfallEventOut> {
  const res = await fetch(
    `${BASE}/fields/${fieldId}/hydrology/rainfall-events/sample`,
    { method: 'POST' },
  )
  return check<RainfallEventOut>(res)
}

export async function importCsvRainfallEvent(
  fieldId: string,
  file: File,
  name: string,
  sourceType: string,
  declared_total_mm?: number | null,
): Promise<RainfallEventOut> {
  const form = new FormData()
  form.append('file', file)
  form.append('name', name)
  form.append('source_type', sourceType)
  if (declared_total_mm != null) {
    form.append('declared_total_mm', String(declared_total_mm))
  }
  const res = await fetch(
    `${BASE}/fields/${fieldId}/hydrology/rainfall-events/import-csv`,
    {
      method: 'POST',
      body: form,
    },
  )
  return check<RainfallEventOut>(res)
}

export async function getHydrologyCatalog(fieldId: string): Promise<CatalogOut> {
  const res = await fetch(`${BASE}/fields/${fieldId}/hydrology/catalog`)
  return check<CatalogOut>(res)
}

export async function listRunoffRuns(
  fieldId: string,
): Promise<RunoffRunOut[]> {
  const res = await fetch(`${BASE}/fields/${fieldId}/hydrology/runoff-runs`)
  return check<RunoffRunOut[]>(res)
}

export async function executeRunoffRun(
  fieldId: string,
  payload: RunoffRunIn,
): Promise<RunoffRunOut> {
  const res = await fetch(`${BASE}/fields/${fieldId}/hydrology/runoff-runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return check<RunoffRunOut>(res)
}

export async function activateRunoffRun(
  fieldId: string,
  runId: string,
): Promise<RunoffRunOut> {
  const res = await fetch(
    `${BASE}/fields/${fieldId}/hydrology/runoff-runs/${runId}/activate`,
    { method: 'POST' },
  )
  return check<RunoffRunOut>(res)
}

export async function compareRunoffScenarios(
  fieldId: string,
  runA: string,
  runB: string,
): Promise<ScenarioComparisonOut> {
  const params = new URLSearchParams({ run_a: runA, run_b: runB })
  const res = await fetch(
    `${BASE}/fields/${fieldId}/hydrology/compare?${params}`,
  )
  return check<ScenarioComparisonOut>(res)
}

export async function getRunoffTimeline(
  fieldId: string,
  runId: string,
): Promise<RunoffTimelineOut> {
  const res = await fetch(
    `${BASE}/fields/${fieldId}/hydrology/runoff-runs/${runId}/timeline`,
  )
  return check<RunoffTimelineOut>(res)
}

export async function listFieldObservations(
  fieldId: string,
): Promise<FieldObservationOut[]> {
  const res = await fetch(`${BASE}/fields/${fieldId}/hydrology/observations`)
  return check<FieldObservationOut[]>(res)
}

export async function createFieldObservation(
  fieldId: string,
  payload: FieldObservationIn,
): Promise<FieldObservationOut> {
  const res = await fetch(`${BASE}/fields/${fieldId}/hydrology/observations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return check<FieldObservationOut>(res)
}

export async function deleteFieldObservation(
  fieldId: string,
  obsId: string,
): Promise<void> {
  const res = await fetch(
    `${BASE}/fields/${fieldId}/hydrology/observations/${obsId}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(`Error HTTP ${res.status}`)
}

export function exportGeoJsonUrl(fieldId: string): string {
  return `${BASE}/fields/${fieldId}/hydrology/export/geojson`
}

export function exportReportUrl(fieldId: string): string {
  return `${BASE}/fields/${fieldId}/hydrology/export/report`
}

export async function runHydrodynamic2DSolver(
  fieldId: string,
  runId: string,
  params: {
    manning_n?: number | null
    ponding_threshold_m?: number
    recession_minutes?: number
  },
): Promise<RunoffRunOut> {
  const res = await fetch(
    `${BASE}/fields/${fieldId}/hydrology/runoff-runs/${runId}/simulate-2d`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    },
  )
  return check<RunoffRunOut>(res)
}

export async function getAgronomicToolkit(
  fieldId: string,
): Promise<AgronomicToolkitOut> {
  const res = await fetch(`${BASE}/fields/${fieldId}/hydrology/toolkit`)
  return check<AgronomicToolkitOut>(res)
}

export async function runAgronomicToolkit(
  fieldId: string,
  payload: AgronomicToolkitIn,
): Promise<AgronomicToolkitOut> {
  const res = await fetch(`${BASE}/fields/${fieldId}/hydrology/toolkit/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return check<AgronomicToolkitOut>(res)
}

export async function getDailyRainfallContext(
  fieldId: string,
  date?: string | null,
): Promise<DailyRainfallContextOut> {
  const q = date ? `?date=${encodeURIComponent(date)}` : ''
  const res = await fetch(`${BASE}/fields/${fieldId}/hydrology/daily-rainfall${q}`)
  return check<DailyRainfallContextOut>(res)
}

export async function simulateDailyRainfall(
  fieldId: string,
  payload: SimulateDailyRainIn,
): Promise<{
  context: DailyRainfallContextOut
  event: RainfallEventOut
  runoff_run: RunoffRunOut
}> {
  const res = await fetch(
    `${BASE}/fields/${fieldId}/hydrology/daily-rainfall/simulate`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
  return check<{
    context: DailyRainfallContextOut
    event: RainfallEventOut
    runoff_run: RunoffRunOut
  }>(res)
}

