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
  twi?: (number | null)[] | null
  spi?: (number | null)[] | null
  agronomic_zone_id?: number[] | null
  runoff_load_mm?: (number | null)[] | null
  cumulative_runoff_m3?: (number | null)[] | null
  water_depth_m?: (number | null)[] | null
  velocity_m_s?: (number | null)[] | null
  soil_loss_t_ha?: (number | null)[] | null
  ndvi?: (number | null)[] | null
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
  twi?: number | null
  spi?: number | null
  agronomic_zone_id?: number | null
  agronomic_zone_label?: string | null
  runoff_generated_q_mm?: number | null
  runoff_load_mm?: number | null
  cumulative_runoff_m3?: number | null
  water_depth_m?: number | null
  velocity_m_s?: number | null
  soil_loss_t_ha?: number | null
  ndvi?: number | null
  row: number
  col: number
  pixel_size_m: number
  crs: string
  source_name: string
  warnings: string[]
}

export interface ProfileIn {
  coordinates: [number, number][]
  step_m?: number | null
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
  burn_lines?: [number, number][][] | null
  burn_depth_m?: number | null
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

export interface AgronomicZoneSummary {
  zone_id: number
  code: string
  label: string
  cells: number
  area_ha: number
  percentage_of_field: number
  mean_elevation_m: number | null
  mean_slope_pct: number | null
  mean_twi: number | null
  mean_spi: number | null
  hydro_behavior: string
  management_guideline: string
}

export interface AgronomicZonationOut {
  twi_field_mean: number
  twi_field_p90: number
  spi_field_mean: number
  spi_field_p90: number
  zones: AgronomicZoneSummary[]
  trafficability: {
    risk_level: string
    soil_group_assumed: string
    estimated_wait_days_high_ground: number
    estimated_wait_days_low_ground: number
    summary: string
  }
  rotaterra_criteria: string[]
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
  agronomic_zonation?: AgronomicZonationOut | null
  warnings: string[]
  limitations: string[]
}

export type RainfallSourceType =
  | 'gauge'
  | 'SMN'
  | 'IMERG'
  | 'CHIRPS'
  | 'ERA5-Land'
  | 'manual'

export interface RainfallIntervalOut {
  timestamp: string
  precipitation_mm: number
  interval_minutes: number
  station_id: string | null
}

export interface RainfallEventManualIn {
  name: string
  total_mm: number
  source_type: RainfallSourceType
  start_at?: string | null
  end_at?: string | null
  source_product?: string | null
  spatial_resolution?: string | null
  quality_flag?: string | null
  uncertainty_note?: string | null
}

export interface RainfallEventOut {
  id: string
  field_id: string
  name: string
  total_mm: number
  source_type: RainfallSourceType
  start_at: string
  end_at: string
  has_time_series: boolean
  interval_minutes: number | null
  intervals: RainfallIntervalOut[]
  max_intensity_mm_h: number | null
  source_metadata: Record<string, unknown>
  warnings: string[]
  created_at: string
}

export type SoilGroup = 'A' | 'B' | 'C' | 'D'
export type AntecedentMoisture = 'dry' | 'medium' | 'wet'

export interface RunoffRunIn {
  name?: string | null
  rainfall_event_id: string
  soil_group: SoilGroup
  cover_code: string
  cover_percent?: number | null
  compaction_high: boolean
  antecedent_moisture: AntecedentMoisture
  lambda_ratio: number
  custom_cn_ii?: number | null
}

export interface CnResultOut {
  precipitation_mm: number
  cn_ii_base: number
  cn_effective: number
  antecedent_moisture: string
  lambda_ratio: number
  potential_retention_s_mm: number
  initial_abstraction_ia_mm: number
  infiltration_after_ia_f_mm: number
  total_retention_losses_mm: number
  runoff_q_mm: number
  runoff_coefficient: number
  mass_balance_error_mm: number
}

export interface SpatialRunoffSummaryOut {
  runoff_generated_q_mm: number
  field_runoff_generated_m3: number
  external_runoff_inflow_m3: number
  total_runoff_supply_m3: number
  potential_depression_retention_m3: number
  net_outflow_potential_m3: number
  max_cell_cumulative_runoff_m3: number
  max_cell_runoff_load_mm: number
  mean_cell_runoff_load_mm: number
  high_concentration_area_ha: number
}

export interface Hydrodynamic2DSummaryOut {
  manning_n: number
  ponding_threshold_m: number
  hydraulic_structures_applied: number
  Effective_runoff_input_mm: number
  infiltration_losses_mm: number
  max_water_depth_in_field_m: number
  mean_max_water_depth_in_field_m: number
  final_retained_water_depth_max_m: number
  max_velocity_in_field_m_s: number
  max_unit_discharge_in_field_m2_s: number
  ponded_area_in_field_ha: number
  ponded_area_in_field_pct: number
  ponded_retained_volume_in_field_m3: number
  domain_input_volume_m3: number
  domain_final_storage_m3: number
  domain_boundary_outflow_m3: number
  mass_balance_relative_error: number
}

export interface RunoffRunOut {
  id: string
  field_id: string
  name: string
  rainfall_event_id: string
  rainfall_event_name: string
  model: string
  processing_version: string
  created_at: string
  is_active: boolean
  field_conditions: Record<string, unknown>
  cn_result: CnResultOut
  spatial_summary: SpatialRunoffSummaryOut
  hydrodynamic_2d_summary?: Hydrodynamic2DSummaryOut | null
  agronomic_zonation?: AgronomicZonationOut | null
  assumptions_and_notes: string[]
  warnings: string[]
  limitations: string[]
}

export interface ScenarioComparisonOut {
  run_a_id: string
  run_a_name: string
  run_b_id: string
  run_b_name: string
  delta_precipitation_mm: number
  delta_cn_effective: number
  delta_initial_abstraction_ia_mm: number
  delta_runoff_q_mm: number
  delta_runoff_q_pct: number | null
  delta_runoff_coefficient: number
  delta_field_runoff_generated_m3: number
  delta_net_outflow_potential_m3: number
  delta_high_concentration_area_ha: number
}

export interface TimelineFrameOut {
  step_index: number
  timestamp: string
  interval_minutes: number
  is_recession: boolean
  interval_precipitation_mm: number
  cumulative_precipitation_mm: number
  interval_infiltration_losses_mm: number
  cumulative_infiltration_losses_mm: number
  interval_runoff_generated_mm: number
  cumulative_runoff_generated_mm: number
  active_transit_lamina_mm: number
  active_transit_volume_m3: number
  depression_retained_mm: number
  depression_retained_volume_m3: number
  interval_outflow_mm: number
  interval_outflow_m3: number
  cumulative_outflow_mm: number
  cumulative_outflow_m3: number
  mass_balance_error_mm: number
  transit_fraction_of_peak: number
}

export interface RunoffTimelineOut {
  run_id: string
  run_name: string
  rainfall_event_id: string
  rainfall_event_name: string
  has_time_series: boolean
  interval_minutes: number | null
  total_steps: number
  rainfall_steps: number
  recession_steps: number
  routing_coefficient_k: number | null
  peak_step_index: number | null
  peak_transit_lamina_mm: number | null
  peak_transit_volume_m3: number | null
  max_mass_balance_error_mm: number | null
  frames: TimelineFrameOut[]
  particle_paths: number[][][]
  warnings: string[]
  limitations: string[]
}

export type ObservationType =
  | 'ponding'
  | 'erosion'
  | 'culvert'
  | 'channel'
  | 'terrace'
  | 'water_depth'

export interface FieldObservationIn {
  observation_type: ObservationType
  lon: number
  lat: number
  notes: string
  value?: number | null
  units?: string | null
  observed_at?: string | null
}

export interface FieldObservationOut {
  id: string
  field_id: string
  observation_type: ObservationType
  label: string
  lon: number
  lat: number
  elevation_m: number | null
  notes: string
  value: number | null
  units: string | null
  observed_at: string
  created_at: string
}

export interface Hydrodynamic2DIn {
  manning_n?: number | null
  ponding_threshold_m: number
  recession_minutes: number
}

export interface AgronomicToolkitIn {
  soil_group: SoilGroup
  cover_code: string
  storm_precipitation_mm: number
  crop_code: string
  environment_zone: 'loma' | 'media_loma' | 'bajo'
  target_yield_t_ha?: number | null
  sequence_a_name?: string
  sequence_a_crops?: string[]
  sequence_b_name?: string
  sequence_b_crops?: string[]
}

export interface AgronomicToolkitOut {
  field_id: string
  processed_at: string
  parameters: Record<string, unknown>
  erosion_usle: {
    r_storm_mj_mm_ha_h: number
    k_factor: number
    c_factor: number
    p_factor: number
    ls_mean_in_field: number
    ls_max_in_field: number
    mean_soil_loss_t_ha: number
    max_soil_loss_t_ha: number
    total_field_soil_loss_tons: number
    gully_initiation_cells: number
    gully_risk_area_ha: number
    erosion_severity: string
  }
  water_balance_monthly: {
    source: string
    available_water_capacity_max_mm: number
    annual_precipitation_mm: number
    annual_et0_mm: number
    deficit_months_count: number
    excess_months_count: number
    final_available_water_mm: number
    final_available_water_pct: number
    months: {
      label: string
      precipitation_mm: number
      et0_mm: number
      available_water_mm: number
      available_water_pct: number
      deficit_mm: number
      excess_drainage_mm: number
      status: string
    }[]
  }
  real_waterlogging_by_date: {
    source: string
    evaluated_days: number
    significant_storms_count: number
    high_waterlogging_events_count: number
    top_historical_events: {
      date: string
      precipitation_mm: number
      prior_5d_rain_mm: number
      antecedent_moisture_amc: string
      runoff_q_mm: number
      estimated_waterlogged_area_ha: number
      waterlogging_risk: string
    }[]
  }
  contour_terraces: {
    mean_field_slope_pct: number
    recommended_vertical_interval_m: number
    recommended_horizontal_spacing_m: number
    terrace_levels_count: number
    estimated_total_terrace_length_m: number
    runoff_before_mm: number
    runoff_after_mm: number
    water_retained_by_terraces_m3: number
    runoff_reduction_pct: number
    soil_loss_before_t_ha: number
    soil_loss_after_t_ha: number
    soil_loss_saved_tons: number
    erosion_reduction_pct: number
    terraces_geojson: GeoJSON.FeatureCollection
  }
  seeding_calculator_inta: {
    crop_label: string
    sowing_window_inta: string
    target_plants_ha: number
    achievement_ratio_pct: number
    seeds_to_sow_ha: number
    seeds_per_linear_m: number
    seed_density_kg_ha: number
    total_seed_kg_for_field: number
    commercial_bags_needed: number
    bag_unit: string
    target_yield_t_ha: number
    nutrients_required_kg_ha: {
      N: number
      P_elemental: number
      P2O5_equiv: number
      S: number
    }
    commercial_fertilizer_guide_kg_ha: {
      MAP_11_52_0_kg_ha: number
      Urea_46_0_0_kg_ha: number
      Yeso_agricola_17S_kg_ha: number
    }
  }
  rotation_comparator_3yr: {
    design_storm_mm: number
    sequence_a: {
      name: string
      mean_cn_3yr: number
      mean_cover_pct_3yr: number
      cumulative_runoff_3yr_mm: number
      cumulative_soil_loss_3yr_t_ha: number
      cumulative_field_soil_loss_3yr_tons: number
    }
    sequence_b: {
      name: string
      mean_cn_3yr: number
      mean_cover_pct_3yr: number
      cumulative_runoff_3yr_mm: number
      cumulative_soil_loss_3yr_t_ha: number
      cumulative_field_soil_loss_3yr_tons: number
    }
    delta_b_vs_a: {
      soil_saved_by_b_tons: number
      runoff_saved_by_b_mm: number
      cover_gain_pct: number
    }
  }
  ndvi_vigor_monitor: {
    source: string
    acquisition_date: string
    mean_ndvi_in_field: number
    low_vigor_area_ha: number
    low_vigor_pct: number
    moderate_vigor_pct: number
    high_vigor_pct: number
    weak_zones_explained_by_waterlogging_or_erosion_pct: number
  }
  frost_risk_sowing: {
    source: string
    mean_meteorological_frost_days_yr: number
    mean_agronomic_frost_days_yr: number
    median_last_spring_frost_date: string
    safe_spring_sowing_start_date: string
    median_first_autumn_frost_date: string
    frost_free_period_days: number
    safe_sowing_windows_by_crop: {
      crop: string
      safe_start: string
      note: string
    }[]
  }
  warnings: string[]
}

export interface CatalogOut {
  covers: Record<string, unknown>[]
  soil_groups: Record<string, unknown>[]
  antecedent_moisture_options: Record<string, unknown>[]
  rainfall_sources: Record<string, unknown>[]
}

export interface HealthOut {
  status: string
  phase: string
  processing_version: string
}

export interface SmnStationOut {
  name: string
  province: string
  latitude: number
  longitude: number
  elevation_m: number
  smn_nro: string
  oaci: string
  distance_km: number
}

export interface DailyRainfallDayOut {
  date: string
  year: number
  month: number
  precipitation_mm: number
  tmin_c: number
  tmax_c: number
  tmean_c: number
  prior_5d_rain_mm: number
  antecedent_moisture_amc: 'dry' | 'medium' | 'wet'
  source: string
  satellite_provider: string
  quality_flag: string
  is_rainy: boolean
}

export interface DailyRainfallContextOut {
  status: 'available' | 'unavailable'
  nearest_smn_station: SmnStationOut
  selected_day: DailyRainfallDayOut | null
  recent_rainy_days: DailyRainfallDayOut[]
  total_days_available: number
  source_label: string
}

export interface SimulateDailyRainIn {
  date: string
  soil_group?: SoilGroup
  cover_code?: string
  cover_percent?: number
  compaction_high?: boolean
}

