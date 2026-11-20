"""Contratos Pydantic de la API v1 (espejados en apps/web/src/types/api.ts)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FieldOut(BaseModel):
    id: str
    name: str
    geometry: dict
    properties: dict
    area_ha: float
    declared_area_ha: float | None
    utm_epsg: int
    centroid: tuple[float, float]
    bbox: tuple[float, float, float, float]
    warnings: list[str]
    created_at: str
    source_file: str | None = None
    has_terrain: bool = False
    has_hydrology: bool = False


class FieldImportOut(BaseModel):
    fields: list[FieldOut]


class DemSourceOut(BaseModel):
    source_id: str
    source_name: str
    source_url: str | None
    license: str | None
    surface_type: str
    nominal_resolution_m: float | None
    vertical_datum: str | None
    vertical_accuracy_m: float | None
    vertical_accuracy_note: str | None
    acquisition_start: str | None
    acquisition_end: str | None
    acquisition_method: str | None


class QualityWarningOut(BaseModel):
    code: str
    level: Literal["info", "advertencia", "critico"]
    message: str


class ElevationStats(BaseModel):
    min: float | None
    max: float | None
    mean: float | None
    range: float | None


class QualityReportOut(BaseModel):
    pixel_size_m: float
    source_pixel_size_m: tuple[float, float]
    crs: str
    vertical_datum: str | None
    vertical_accuracy_m: float | None
    surface_type: str
    width: int
    height: int
    buffer_m: float
    cells_in_field: int
    cells_in_area: int
    nodata_pct_field: float
    nodata_pct_area: float
    elevation_field: ElevationStats
    elevation_area: ElevationStats
    field_area_ha: float
    warnings: list[QualityWarningOut]


class TerrainOut(BaseModel):
    field_id: str
    processing_version: str
    processed_at: str
    parameters: dict
    source: DemSourceOut
    quality: QualityReportOut
    files: dict
    limitations: list[str]


class MeshOut(BaseModel):
    rows: int
    cols: int
    decimation: int
    pixel_size_m: float
    mesh_cell_size_m: float
    z_min: float | None
    z_max: float | None
    lon: list[float]
    lat: list[float]
    z: list[float | None]
    in_field: list[bool]
    slope_pct: list[float | None] = []
    hillshade: list[float | None] = []
    sink_depth_m: list[float | None] | None = None
    mfd_area_ha: list[float | None] | None = None
    d8_area_ha: list[float | None] | None = None
    d8_code: list[int] | None = None
    subbasin_id: list[int] | None = None
    twi: list[float | None] | None = None
    spi: list[float | None] | None = None
    agronomic_zone_id: list[int] | None = None
    runoff_load_mm: list[float | None] | None = None
    cumulative_runoff_m3: list[float | None] | None = None
    water_depth_m: list[float | None] | None = None
    velocity_m_s: list[float | None] | None = None
    soil_loss_t_ha: list[float | None] | None = None
    ndvi: list[float | None] | None = None
    boundary: list[list[list[float | None]]]


class PointOut(BaseModel):
    lon: float
    lat: float
    x_utm: float
    y_utm: float
    inside_dem: bool
    inside_field: bool | None
    elevation_m: float | None
    cell_elevation_m: float | None
    slope_pct: float | None
    slope_deg: float | None
    aspect_deg: float | None
    hillshade: float | None = None
    sink_depth_m: float | None = None
    depression_id: int | None = None
    d8_code: int | None = None
    d8_direction: str | None = None
    d8_azimuth_deg: float | None = None
    d8_area_m2: float | None = None
    d8_area_ha: float | None = None
    mfd_area_m2: float | None = None
    mfd_area_ha: float | None = None
    subbasin_id: int | None = None
    twi: float | None = None
    spi: float | None = None
    agronomic_zone_id: int | None = None
    agronomic_zone_label: str | None = None
    runoff_generated_q_mm: float | None = None
    runoff_load_mm: float | None = None
    cumulative_runoff_m3: float | None = None
    water_depth_m: float | None = None
    velocity_m_s: float | None = None
    soil_loss_t_ha: float | None = None
    ndvi: float | None = None
    row: int
    col: int
    pixel_size_m: float
    crs: str
    source_name: str
    warnings: list[str]


class ProfileIn(BaseModel):
    coordinates: list[tuple[float, float]] = Field(..., min_length=2, max_length=500)
    step_m: float | None = Field(None, gt=0, le=1000)

    @field_validator("coordinates")
    @classmethod
    def _rango(cls, v):
        for lon, lat in v:
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError("Coordenadas fuera de rango (lon, lat en grados)")
        return v


class ProfileSample(BaseModel):
    distance_m: float
    elevation_m: float | None
    lon: float
    lat: float


class ProfileSummary(BaseModel):
    length_m: float
    step_m: float
    samples: int
    valid_samples: int
    min_m: float | None
    max_m: float | None
    range_m: float | None
    start_end_diff_m: float | None
    mean_abs_slope_pct: float | None


class ProfileOut(BaseModel):
    summary: ProfileSummary
    vertices_distance_m: list[float]
    samples: list[ProfileSample]
    pixel_size_m: float
    source_name: str
    warnings: list[str]


class ContoursOut(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    interval_m: float
    features: list[dict]


class HydrologyRunIn(BaseModel):
    conditioning_mode: Literal["preserve", "fill_small", "fill_all"] = "fill_small"
    max_fill_depth_m: float = Field(0.35, ge=0.0, le=5.0)
    max_fill_area_m2: float = Field(4500.0, ge=0.0, le=500_000.0)
    mfd_exponent: float = Field(1.1, ge=0.5, le=5.0)
    stream_threshold_ha: float | None = Field(None, gt=0.01, le=5000.0)
    routing_basis: Literal["MFD", "D8"] = "MFD"
    contour_interval_m: float | None = Field(None, gt=0.1, le=200.0)
    burn_lines: list[list[tuple[float, float]]] | None = None
    burn_depth_m: float = Field(0.5, ge=0.0, le=5.0)


class DepressionOut(BaseModel):
    id: int
    cells: int
    area_m2: float
    area_ha: float
    max_depth_m: float
    mean_depth_m: float
    volume_m3: float
    pour_point_elevation_m: float
    min_elevation_m: float
    centroid_lon: float
    centroid_lat: float
    in_field: bool
    is_spurious_candidate: bool
    filled_in_run: bool


class OutletOut(BaseModel):
    id: int
    type: str
    lon: float
    lat: float
    elevation_m: float
    d8_direction: str
    contributing_area_mfd_ha: float
    contributing_area_d8_ha: float
    subbasin_total_ha: float
    subbasin_in_field_ha: float
    subbasin_external_inflow_ha: float


class HydrologySummaryOut(BaseModel):
    depressions_count: int
    depressions_in_field_count: int
    depressions_filled_count: int
    total_depression_area_in_field_ha: float
    total_depression_volume_in_field_m3: float
    max_depression_depth_in_field_m: float
    max_mfd_area_in_field_ha: float
    max_d8_area_in_field_ha: float
    stream_segments_count: int
    total_stream_length_m: float
    outlets_count: int
    external_inflow_ha: float
    mfd_mass_balance_error: float


class HydrologyOut(BaseModel):
    field_id: str
    processing_version: str
    processed_at: str
    parameters: dict
    summary: HydrologySummaryOut
    depressions: list[DepressionOut]
    outlets: list[OutletOut]
    drainage_network: dict
    contours: ContoursOut
    agronomic_zonation: dict | None = None
    warnings: list[str]
    limitations: list[str]


class RainfallIntervalOut(BaseModel):
    timestamp: str
    precipitation_mm: float
    interval_minutes: int
    station_id: str | None = None


class RainfallEventManualIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    total_mm: float = Field(..., gt=0.0, le=1500.0)
    source_type: Literal["gauge", "SMN", "IMERG", "CHIRPS", "ERA5-Land", "manual"] = "manual"
    start_at: str | None = None
    end_at: str | None = None
    source_product: str | None = None
    spatial_resolution: str | None = None
    quality_flag: str | None = None
    uncertainty_note: str | None = None


class RainfallEventOut(BaseModel):
    id: str
    field_id: str
    name: str
    total_mm: float
    source_type: str
    start_at: str
    end_at: str
    has_time_series: bool
    interval_minutes: int | None = None
    intervals: list[RainfallIntervalOut] = []
    max_intensity_mm_h: float | None = None
    source_metadata: dict
    warnings: list[str]
    created_at: str


class SmnStationOut(BaseModel):
    name: str
    province: str
    latitude: float
    longitude: float
    elevation_m: float
    smn_nro: str
    oaci: str
    distance_km: float


class DailyRainfallDayOut(BaseModel):
    date: str
    year: int
    month: int
    precipitation_mm: float
    tmin_c: float
    tmax_c: float
    tmean_c: float
    prior_5d_rain_mm: float
    antecedent_moisture_amc: Literal["dry", "medium", "wet"]
    source: str
    satellite_provider: str
    quality_flag: str
    is_rainy: bool


class DailyRainfallContextOut(BaseModel):
    status: Literal["available", "unavailable"]
    nearest_smn_station: SmnStationOut
    selected_day: DailyRainfallDayOut | None = None
    recent_rainy_days: list[DailyRainfallDayOut] = []
    total_days_available: int = 0
    source_label: str


class SimulateDailyRainIn(BaseModel):
    date: str = Field(..., description="Fecha del día a simular (YYYY-MM-DD)")
    soil_group: Literal["A", "B", "C", "D"] = "B"
    cover_code: str = "soja_maiz_sd_buena"
    cover_percent: float | None = Field(60.0, ge=0.0, le=100.0)
    compaction_high: bool = False


class RunoffRunIn(BaseModel):
    name: str | None = Field(None, max_length=140)
    rainfall_event_id: str
    soil_group: Literal["A", "B", "C", "D"] = "B"
    cover_code: str = "soja_maiz_sd_buena"
    cover_percent: float | None = Field(60.0, ge=0.0, le=100.0)
    compaction_high: bool = False
    antecedent_moisture: Literal["dry", "medium", "wet"] = "medium"
    lambda_ratio: float = Field(0.2, ge=0.01, le=0.5)
    custom_cn_ii: float | None = Field(None, ge=30.0, le=98.0)

    @field_validator("cover_code")
    @classmethod
    def _val_cover(cls, v: str) -> str:
        from geoprocessing.rainfall.nrcs_cn import TABLE_CN_II
        if v not in TABLE_CN_II:
            raise ValueError(f"cover_code '{v}' no reconocido. Opciones válidas: {list(TABLE_CN_II.keys())}")
        return v


class CnResultOut(BaseModel):
    precipitation_mm: float
    cn_ii_base: float
    cn_effective: float
    antecedent_moisture: str
    lambda_ratio: float
    potential_retention_s_mm: float
    initial_abstraction_ia_mm: float
    infiltration_after_ia_f_mm: float
    total_retention_losses_mm: float
    runoff_q_mm: float
    runoff_coefficient: float
    mass_balance_error_mm: float


class SpatialRunoffSummaryOut(BaseModel):
    runoff_generated_q_mm: float
    field_runoff_generated_m3: float
    external_runoff_inflow_m3: float
    total_runoff_supply_m3: float
    potential_depression_retention_m3: float
    net_outflow_potential_m3: float
    max_cell_cumulative_runoff_m3: float
    max_cell_runoff_load_mm: float
    mean_cell_runoff_load_mm: float
    high_concentration_area_ha: float


class RunoffRunOut(BaseModel):
    id: str
    field_id: str
    name: str
    rainfall_event_id: str
    rainfall_event_name: str
    model: str
    processing_version: str
    created_at: str
    is_active: bool
    field_conditions: dict
    cn_result: CnResultOut
    spatial_summary: SpatialRunoffSummaryOut
    hydrodynamic_2d_summary: dict | None = None
    agronomic_zonation: dict | None = None
    assumptions_and_notes: list[str]
    warnings: list[str]
    limitations: list[str]


class ScenarioComparisonOut(BaseModel):
    run_a_id: str
    run_a_name: str
    run_b_id: str
    run_b_name: str
    delta_precipitation_mm: float
    delta_cn_effective: float
    delta_initial_abstraction_ia_mm: float
    delta_runoff_q_mm: float
    delta_runoff_q_pct: float | None
    delta_runoff_coefficient: float
    delta_field_runoff_generated_m3: float
    delta_net_outflow_potential_m3: float
    delta_high_concentration_area_ha: float


class TimelineFrameOut(BaseModel):
    step_index: int
    timestamp: str
    interval_minutes: int
    is_recession: bool
    interval_precipitation_mm: float
    cumulative_precipitation_mm: float
    interval_infiltration_losses_mm: float
    cumulative_infiltration_losses_mm: float
    interval_runoff_generated_mm: float
    cumulative_runoff_generated_mm: float
    active_transit_lamina_mm: float
    active_transit_volume_m3: float
    depression_retained_mm: float
    depression_retained_volume_m3: float
    interval_outflow_mm: float
    interval_outflow_m3: float
    cumulative_outflow_mm: float
    cumulative_outflow_m3: float
    mass_balance_error_mm: float
    transit_fraction_of_peak: float


class RunoffTimelineOut(BaseModel):
    run_id: str
    run_name: str
    rainfall_event_id: str
    rainfall_event_name: str
    has_time_series: bool
    interval_minutes: int | None = None
    total_steps: int
    rainfall_steps: int
    recession_steps: int
    routing_coefficient_k: float | None = None
    peak_step_index: int | None = None
    peak_transit_lamina_mm: float | None = None
    peak_transit_volume_m3: float | None = None
    max_mass_balance_error_mm: float | None = None
    frames: list[TimelineFrameOut] = []
    particle_paths: list[list[list[float]]] = []
    warnings: list[str]
    limitations: list[str]


ObservationType = Literal[
    "ponding",
    "erosion",
    "culvert",
    "channel",
    "terrace",
    "water_depth",
]


class FieldObservationIn(BaseModel):
    observation_type: ObservationType
    lon: float = Field(..., ge=-180.0, le=180.0)
    lat: float = Field(..., ge=-90.0, le=90.0)
    notes: str = Field(..., min_length=2, max_length=400)
    value: float | None = None
    units: str | None = Field(None, max_length=32)
    observed_at: str | None = None


class FieldObservationOut(BaseModel):
    id: str
    field_id: str
    observation_type: ObservationType
    label: str
    lon: float
    lat: float
    elevation_m: float | None
    notes: str
    value: float | None
    units: str | None
    observed_at: str
    created_at: str


class Hydrodynamic2DIn(BaseModel):
    manning_n: float | None = Field(None, ge=0.015, le=0.50)
    ponding_threshold_m: float = Field(0.05, ge=0.01, le=2.0)
    recession_minutes: int = Field(30, ge=5, le=360)


class AgronomicToolkitIn(BaseModel):
    soil_group: Literal["A", "B", "C", "D"] = "B"
    cover_code: str = "soja_maiz_sd_buena"
    storm_precipitation_mm: float = Field(80.0, gt=0.0, le=1000.0)
    crop_code: str = "maiz_temprano"
    environment_zone: Literal["loma", "media_loma", "bajo"] = "media_loma"
    target_yield_t_ha: float | None = Field(None, gt=0.5, le=25.0)
    sequence_a_name: str = "Secuencia A — Monocultivo / Baja Cobertura"
    sequence_a_crops: list[str] = [
        "soja_maiz_convencional",
        "barbecho_suelo_desnudo",
        "soja_maiz_convencional",
    ]
    sequence_b_name: str = "Secuencia B — Rotación Sustentable RotaTerra (SD + Cobertura)"
    sequence_b_crops: list[str] = [
        "soja_maiz_sd_buena",
        "trigo_cereal_invierno_sd",
        "cultivo_cobertura_vicia_centeno",
    ]


class Hydrodynamic2DSummaryOut(BaseModel):
    manning_n: float
    ponding_threshold_m: float
    hydraulic_structures_applied: int
    Effective_runoff_input_mm: float
    infiltration_losses_mm: float
    max_water_depth_in_field_m: float
    mean_max_water_depth_in_field_m: float
    final_retained_water_depth_max_m: float
    max_velocity_in_field_m_s: float
    max_unit_discharge_in_field_m2_s: float
    ponded_area_in_field_ha: float
    ponded_area_in_field_pct: float
    ponded_retained_volume_in_field_m3: float
    domain_input_volume_m3: float
    domain_final_storage_m3: float
    domain_boundary_outflow_m3: float
    mass_balance_relative_error: float


class AgronomicZonationOut(BaseModel):
    twi_field_mean: float
    twi_field_p90: float
    spi_field_mean: float
    spi_field_p90: float
    zones: list[dict]
    trafficability: dict
    rotaterra_criteria: list[str]


class AgronomicToolkitOut(BaseModel):
    field_id: str
    processed_at: str
    parameters: dict
    erosion_usle: dict
    water_balance_monthly: dict
    real_waterlogging_by_date: dict
    contour_terraces: dict
    seeding_calculator_inta: dict
    rotation_comparator_3yr: dict
    ndvi_vigor_monitor: dict
    frost_risk_sowing: dict
    warnings: list[str]


class CatalogOut(BaseModel):
    covers: list[dict]
    soil_groups: list[dict]
    antecedent_moisture_options: list[dict]
    rainfall_sources: list[dict]


class HealthOut(BaseModel):
    status: str
    phase: str
    processing_version: str
