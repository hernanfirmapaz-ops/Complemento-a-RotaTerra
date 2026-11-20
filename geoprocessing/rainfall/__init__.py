"""Eventos de precipitación, validación de series temporales CSV y modelo NRCS Curve Number (Fase 2)."""

from geoprocessing.rainfall.daily_national import (
    find_nearest_smn_station,
    get_field_daily_rainfall_context,
)
from geoprocessing.rainfall.events import RainfallInterval, RainfallValidationError
from geoprocessing.rainfall.nrcs_cn import compute_nrcs_cn, lookup_cn_ii

__all__ = [
    "RainfallInterval",
    "RainfallValidationError",
    "compute_nrcs_cn",
    "lookup_cn_ii",
    "find_nearest_smn_station",
    "get_field_daily_rainfall_context",
]
