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
    warnings: list[str]
    limitations: list[str]
