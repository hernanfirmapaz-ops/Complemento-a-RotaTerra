/** Contratos TypeScript de la API v1 (espejados con `services/api/app/schemas.py`). */

export interface FieldOut {
  id: string
  name: string
  geometry: {
    type: 'MultiPolygon' | 'Polygon'
    coordinates: number[][][][] | number[][][]
  }
  properties: Record<string, unknown>
  area_ha: number
  declared_area_ha: number | null
  utm_epsg: number
  centroid: [number, number]
  bbox: [number, number, number, number]
  warnings: string[]
  created_at: string
  source_file: string | null
  has_terrain: boolean
}

export interface DemSourceOut {
  source_id: string
  source_name: string
  source_url: string | null
  license: string | null
  surface_type: string
  nominal_resolution_m: number | null
  vertical_datum: string | null
  vertical_accuracy_m: number | null
  vertical_accuracy_note: string | null
  acquisition_start: string | null
  acquisition_end: string | null
  acquisition_method: string | null
}

export interface QualityWarningOut {
  code: string
  level: 'info' | 'advertencia' | 'critico'
  message: string
}

export interface ElevationStats {
  min: number | null
  max: number | null
  mean: number | null
  range: number | null
}

export interface QualityReportOut {
  pixel_size_m: number
  source_pixel_size_m: [number, number]
  crs: string
  vertical_datum: string | null
  vertical_accuracy_m: number | null
  surface_type: string
  width: number
  height: number
  buffer_m: number
  cells_in_field: number
  cells_in_area: number
  nodata_pct_field: number
  nodata_pct_area: number
  elevation_field: ElevationStats
  elevation_area: ElevationStats
  field_area_ha: number
  warnings: QualityWarningOut[]
}

export interface TerrainOut {
  field_id: string
  processing_version: string
  processed_at: string
  parameters: Record<string, unknown>
  source: DemSourceOut
  quality: QualityReportOut
  files: Record<string, string>
  limitations: string[]
}

export interface MeshOut {
  rows: number
  cols: number
  decimation: number
  pixel_size_m: number
  mesh_cell_size_m: number
  z_min: number | null
  z_max: number | null
  lon: number[]
  lat: number[]
  z: (number | null)[]
  in_field: boolean[]
  boundary: (number | null)[][][]
}

export interface PointOut {
  lon: number
  lat: number
  x_utm: number
  y_utm: number
  inside_dem: boolean
  inside_field: boolean | null
  elevation_m: number | null
  cell_elevation_m: number | null
  slope_pct: number | null
  slope_deg: number | null
  aspect_deg: number | null
  row: number
  col: number
  pixel_size_m: number
  crs: string
  source_name: string
  warnings: string[]
}

export interface ProfileSample {
  distance_m: number
  elevation_m: number | null
  lon: number
  lat: number
}

export interface ProfileSummary {
  length_m: number
  step_m: number
  samples: number
  valid_samples: number
  min_m: number | null
  max_m: number | null
  range_m: number | null
  start_end_diff_m: number | null
  mean_abs_slope_pct: number | null
}

export interface ProfileOut {
  summary: ProfileSummary
  vertices_distance_m: number[]
  samples: ProfileSample[]
  pixel_size_m: number
  source_name: string
  warnings: string[]
}
