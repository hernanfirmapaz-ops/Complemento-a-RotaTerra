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
  has_hydrology: boolean
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
  message: str
}

type str = string

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
  slope_pct: (number | null)[]
  hillshade: (number | null)[]
  sink_depth_m?: (number | null)[] | null
  mfd_area_ha?: (number | null)[] | null
  d8_area_ha?: (number | null)[] | null
  d8_code?: number[] | null
  subbasin_id?: number[] | null
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
  hillshade: number | null
  sink_depth_m: number | null
  depression_id: number | null
  d8_code: number | null
  d8_direction: string | null
  d8_azimuth_deg: number | null
  d8_area_m2: number | null
  d8_area_ha: number | null
  mfd_area_m2: number | null
  mfd_area_ha: number | null
  subbasin_id: number | null
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

export type ConditioningMode = 'preserve' | 'fill_small' | 'fill_all'

export interface HydrologyRunIn {
  conditioning_mode: ConditioningMode
  max_fill_depth_m: number
  max_fill_area_m2: number
  mfd_exponent: number
  stream_threshold_ha?: number | null
  routing_basis: 'MFD' | 'D8'
  contour_interval_m?: number | null
}

export interface DepressionOut {
  id: number
  cells: number
  area_m2: number
  area_ha: number
  max_depth_m: number
  mean_depth_m: number
  volume_m3: number
  pour_point_elevation_m: number
  min_elevation_m: number
  centroid_lon: number
  centroid_lat: number
  in_field: boolean
  is_spurious_candidate: boolean
  filled_in_run: boolean
}

export interface OutletOut {
  id: number
  type: string
  lon: number
  lat: number
  elevation_m: number
  d8_direction: string
  contributing_area_mfd_ha: number
  contributing_area_d8_ha: number
  subbasin_total_ha: number
  subbasin_in_field_ha: number
  subbasin_external_inflow_ha: number
}

export interface HydrologySummaryOut {
  depressions_count: number
  depressions_in_field_count: number
  depressions_filled_count: number
  total_depression_area_in_field_ha: number
  total_depression_volume_in_field_m3: number
  max_depression_depth_in_field_m: number
  max_mfd_area_in_field_ha: number
  max_d8_area_in_field_ha: number
  stream_segments_count: number
  total_stream_length_m: number
  outlets_count: number
  external_inflow_ha: number
  mfd_mass_balance_error: number
}

export interface ContoursOut {
  type: 'FeatureCollection'
  interval_m: number
  features: GeoJSON.Feature[]
}

export interface HydrologyOut {
  field_id: string
  processing_version: string
  processed_at: string
  parameters: Record<string, unknown>
  summary: HydrologySummaryOut
  depressions: DepressionOut[]
  outlets: OutletOut[]
  drainage_network: GeoJSON.FeatureCollection & {
    threshold_ha?: number
    basis?: string
  }
  contours: ContoursOut
  warnings: string[]
  limitations: string[]
}
