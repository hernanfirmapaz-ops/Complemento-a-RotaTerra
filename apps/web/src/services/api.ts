/** Cliente HTTP de la API v1 (`/api/v1`). */

import type {
  FieldOut,
  HydrologyOut,
  HydrologyRunIn,
  MeshOut,
  PointOut,
  ProfileOut,
  TerrainOut,
} from '../types/api'

const BASE = '/api/v1'

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

export async function loadSampleField(): Promise<FieldOut[]> {
  const res = await fetch(`${BASE}/fields/sample`, { method: 'POST' })
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
): Promise<ProfileOut> {
  const res = await fetch(`${BASE}/fields/${fieldId}/terrain/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ coordinates }),
  })
  return check<ProfileOut>(res)
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
