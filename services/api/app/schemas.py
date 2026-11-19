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
