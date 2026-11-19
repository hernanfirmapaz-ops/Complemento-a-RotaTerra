"""Informe de calidad y resolución efectiva del DEM (SDD §6.2 paso 8 y §11.2).

Los umbrales de aviso son SUPUESTOS de arranque, documentados y ajustables; no son normas.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from geoprocessing.dem.sources import DemSourceInfo
from geoprocessing.fields import field_utm_geometry

# SUPUESTOS (calibrar con usuarios y casos reales)
CELDAS_CRITICO = 25  # menos celdas dentro del lote: el relieve del lote no se puede describir
CELDAS_BAJO = 400  # menos celdas: solo la forma general del relieve
PIXEL_MICRORELIEVE_M = 5.0  # con píxeles mayores no se representan surcos, cunetas ni microdepresiones
NODATA_ALTO_PCT = 5.0


@dataclass
class QualityWarning:
    code: str
    level: str  # "info" | "advertencia" | "critico"
    message: str


@dataclass
class QualityReport:
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
    elevation_field: dict  # min, max, mean, range (m)
    elevation_area: dict
    field_area_ha: float
    warnings: list[QualityWarning] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def field_mask(geometry_4326: dict, epsg: int, transform, shape: tuple[int, int]) -> np.ndarray:
    """True en las celdas cuyo centro cae dentro del lote."""
    from rasterio.features import geometry_mask

    lote = field_utm_geometry(geometry_4326, epsg)
    return geometry_mask([lote.__geo_interface__], out_shape=shape, transform=transform, invert=True,
                         all_touched=False)


def _stats(valores: np.ndarray) -> dict:
    v = valores[np.isfinite(valores)]
    if v.size == 0:
        return {"min": None, "max": None, "mean": None, "range": None}
    return {"min": round(float(v.min()), 2), "max": round(float(v.max()), 2),
            "mean": round(float(v.mean()), 2), "range": round(float(v.max() - v.min()), 2)}


def build_quality_report(dem: np.ndarray, transform, crs: str, mascara_lote: np.ndarray, area_ha: float,
                         fuente: DemSourceInfo, source_pixel_size_m: tuple[float, float],
                         buffer_m: float) -> QualityReport:
    pixel = round(abs(transform.a), 3)
    celdas_lote = int(mascara_lote.sum())
    validos = np.isfinite(dem)
    nodata_lote = 100 * (1 - validos[mascara_lote].mean()) if celdas_lote else 100.0
    nodata_area = 100 * (1 - validos.mean())
    est_lote = _stats(dem[mascara_lote])
    est_area = _stats(dem)

    avisos: list[QualityWarning] = []
    if celdas_lote < CELDAS_CRITICO:
        avisos.append(QualityWarning(
            "resolucion_insuficiente", "critico",
            f"Resolución insuficiente: solo {celdas_lote} celdas de {pixel:.0f} m caen dentro del lote. "
            "El DEM no puede describir el relieve interno del lote."))
    elif celdas_lote < CELDAS_BAJO:
        avisos.append(QualityWarning(
            "resolucion_baja", "advertencia",
            f"Resolución baja: {celdas_lote} celdas de {pixel:.0f} m dentro del lote. "
            "Solo representa la forma general del relieve."))
    if pixel > PIXEL_MICRORELIEVE_M:
        avisos.append(QualityWarning(
            "sin_microrelieve", "advertencia",
            f"Con píxeles de {pixel:.0f} m no se representan surcos, cunetas, camellones ni microdepresiones."))
    if fuente.surface_type == "DSM":
        avisos.append(QualityWarning(
            "modelo_superficie", "advertencia",
            "Es un modelo de superficie (DSM): incluye árboles, construcciones y otros objetos, no solo el suelo."))
    elif fuente.surface_type == "desconocido":
        avisos.append(QualityWarning(
            "tipo_superficie_desconocido", "advertencia",
            "No se declaró si el DEM es de terreno desnudo (DTM) o de superficie (DSM)."))
    if not fuente.vertical_datum:
        avisos.append(QualityWarning("datum_desconocido", "advertencia", "Datum vertical no declarado."))
    if fuente.vertical_accuracy_m is None:
        avisos.append(QualityWarning("precision_desconocida", "advertencia", "Precisión vertical no declarada."))
    elif est_lote["range"] is not None and est_lote["range"] <= 2 * fuente.vertical_accuracy_m:
        avisos.append(QualityWarning(
            "desnivel_vs_precision", "advertencia",
            f"El desnivel dentro del lote ({est_lote['range']:.1f} m) es comparable a la precisión vertical "
            f"declarada (±{fuente.vertical_accuracy_m:g} m): las diferencias de cota pueden no ser significativas."))
    if nodata_lote > NODATA_ALTO_PCT:
        avisos.append(QualityWarning(
            "nodata_alto", "critico",
            f"{nodata_lote:.1f} % del lote sin dato de elevación. No se interpolaron los vacíos."))
    elif nodata_lote > 0:
        avisos.append(QualityWarning(
            "nodata", "advertencia", f"{nodata_lote:.1f} % del lote sin dato. No se interpolaron los vacíos."))
    if not fuente.acquisition_start:
        avisos.append(QualityWarning("fecha_desconocida", "info", "Fecha de adquisición no disponible."))

    return QualityReport(
        pixel_size_m=pixel, source_pixel_size_m=source_pixel_size_m, crs=crs,
        vertical_datum=fuente.vertical_datum, vertical_accuracy_m=fuente.vertical_accuracy_m,
        surface_type=fuente.surface_type, width=dem.shape[1], height=dem.shape[0], buffer_m=buffer_m,
        cells_in_field=celdas_lote, cells_in_area=int(dem.size),
        nodata_pct_field=round(float(nodata_lote), 2), nodata_pct_area=round(float(nodata_area), 2),
        elevation_field=est_lote, elevation_area=est_area, field_area_ha=area_ha, warnings=avisos,
    )
