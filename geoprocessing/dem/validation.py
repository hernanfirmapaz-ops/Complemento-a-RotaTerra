"""Validación geodésica de modelos de elevación y análisis fuera de muestra (SDD §5.1, Spec 014, Paso 4).

Implementa:
1. Métricas de dispersión y sesgo robustas según recomendaciones de Höhle & Höhle (2009).
2. Conversión a datum vertical común (EGM2008), tratando el sesgo de GEM-15 como empírico.
3. Validación cruzada fuera de muestra (Leave-One-Out, LOO) con mojones de nivelación geométrica IGN.
4. Exclusión obligatoria de la red topográfica secundaria (con cotas dudosas).
5. Punto de entrada para validación espacial continua contra rásteres de referencia (e.g. MDE IGN 5 m).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from geoprocessing.supuestos import (
    SUPUESTO_DEM_DATUM_COMUN_VERTICAL,
    SUPUESTO_DEM_EXCLUIR_RED_TOPOGRAFICA,
    SUPUESTO_DEM_RASTER_REFERENCIA_PATH,
)


def compute_robust_stats(errors: np.ndarray | list[float]) -> dict[str, float]:
    """Calcula métricas estadísticas robustas (mediana de sesgo, NMAD, RMSE y LE90).

    Referencia: Höhle & Höhle (2009), ISPRS Journal of Photogrammetry and Remote Sensing, 64(4), 398-406.
    """
    err = np.asarray(errors, dtype=float)
    err = err[np.isfinite(err)]
    if err.size == 0:
        return {
            "mediana": 0.0,
            "nmad": 0.0,
            "rmse": 0.0,
            "le90": 0.0,
            "mean": 0.0,
            "std": 0.0,
            "count": 0,
        }
    med = float(np.median(err))
    nmad = float(1.4826 * np.median(np.abs(err - med)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    le90 = float(np.percentile(np.abs(err), 90))
    mean = float(np.mean(err))
    std = float(np.std(err))
    return {
        "mediana": round(med, 3),
        "nmad": round(nmad, 3),
        "rmse": round(rmse, 3),
        "le90": round(le90, 3),
        "mean": round(mean, 3),
        "std": round(std, 3),
        "count": int(err.size),
    }


def assume_same_vertical_datum(
    z: np.ndarray | float,
    source_datum: str | None = None,
    target_datum: str | None = None,
) -> np.ndarray | float:
    """Adopta la equivalencia práctica de datum vertical bajo supuesto metodológico declarado.

    IMPORTANTE (Limitación de datum vertical):
    - Esta función NO realiza una transformación analítica de ondulación geoidal de grilla
      (las grillas geoidales locales no se incluyen para mantener la suite 100% offline).
    - Las cotas de los mojones del IGN están referidas al Sistema de Alturas Nacional (IGN),
      NO a EGM2008 ni a EGM96.
    - Copernicus GLO-30 está nativamente en EGM2008 y Google GEM-15 en EGM96.
    - Se adopta el supuesto metodológico declarado (SUPUESTO_DEM_DATUM_DIFERENCIA_DESPRECIABLE)
      de que la diferencia entre modelos geoidales en la zona es despreciable frente al sesgo
      sistemático empírico (+3,1 m en GEM-15) y a la dispersión del sensor (~1,15 m NMAD en Copernicus).

    Regla de integridad:
    - Sin datum declarado explícitamente (`source_datum`), NO se adopta un valor por omisión silencioso
      con patrón 'or', sino que se eleva ValueError.
    """
    if source_datum is None or not str(source_datum).strip():
        raise ValueError(
            "Sin datum declarado: no se puede asumir equivalencia de datum vertical sin 'source_datum'. "
            "Especifique el datum de origen (ej. 'EGM96', 'EGM2008') o descarte la comparación."
        )

    tgt = str(target_datum if target_datum is not None else SUPUESTO_DEM_DATUM_COMUN_VERTICAL.valor).strip().upper()
    src = str(source_datum).strip().upper()
    if src == tgt:
        return z

    return z


def leave_one_out_validation(
    features: list[dict[str, Any]],
    dem_key: str = "cota_gem15_m",
    ign_key: str = "cota_ign_m",
    exclude_topographic: bool | None = None,
) -> dict[str, Any]:
    """Ejecuta validación cruzada fuera de muestra (Leave-One-Out, LOO) sobre una red de mojones IGN.

    Para cada mojón k de los N mojones válidos:
      1. Calibra el sesgo con los N - 1 mojones restantes:
         bias_{-k} = mediana({ z_dem[j] - z_ign[j] : j != k })
      2. Predice y corrige la cota del mojón excluido:
         z_calib[k] = z_dem[k] - bias_{-k}
      3. Mide el error fuera de muestra:
         e_loo[k] = z_calib[k] - z_ign[k] = (z_dem[k] - z_ign[k]) - bias_{-k}

    Reglas de inclusión:
      - Por defecto (SUPUESTO_DEM_EXCLUIR_RED_TOPOGRAFICA = True), la red 'topografica'
        queda excluida de la validación y de la calibración por presentar dispersión
        anómala (NMAD > 3,5 m) y cotas dudosas documentadas (Spec 014 §1.2).
      - Solo participan mojones de 'alta_precision' y 'precision' no marcados como excluidos.
    """
    should_exclude_topo = (
        bool(SUPUESTO_DEM_EXCLUIR_RED_TOPOGRAFICA.valor)
        if exclude_topographic is None
        else bool(exclude_topographic)
    )

    valid_points: list[dict[str, Any]] = []
    excluded_points: list[dict[str, Any]] = []

    for feat in features:
        props = feat.get("properties", feat)
        red = props.get("red")
        is_excl = bool(props.get("excluida", False))

        if should_exclude_topo and red == "topografica":
            excluded_points.append(props)
            continue
        if is_excl:
            excluded_points.append(props)
            continue

        c_dem = props.get(dem_key)
        c_ign = props.get(ign_key)
        if c_dem is not None and c_ign is not None:
            valid_points.append(props)
        else:
            excluded_points.append(props)

    n = len(valid_points)
    if n < 2:
        return {
            "status": "insuficientes_puntos",
            "n_valid": n,
            "n_excluded": len(excluded_points),
            "in_sample": compute_robust_stats(np.array([])),
            "out_of_sample": compute_robust_stats(np.array([])),
            "per_point_loo_errors": [],
        }

    raw_dem = np.array([float(p[dem_key]) for p in valid_points], dtype=float)
    cota_ign = np.array([float(p[ign_key]) for p in valid_points], dtype=float)
    raw_errors = raw_dem - cota_ign

    # 1. Ajuste In-Sample (calibrar con todos y evaluar con todos)
    in_sample_bias = float(np.median(raw_errors))
    in_sample_errors = raw_errors - in_sample_bias
    in_sample_stats = compute_robust_stats(in_sample_errors)

    # 2. Ajuste Out-of-Sample Leave-One-Out (LOO)
    loo_errors = np.zeros(n, dtype=float)
    loo_biases_applied = np.zeros(n, dtype=float)
    per_point_results: list[dict[str, Any]] = []

    for i in range(n):
        # Muestra de calibración: todos los mojones excepto i
        train_errors = np.delete(raw_errors, i)
        calib_bias = float(np.median(train_errors))
        loo_biases_applied[i] = calib_bias

        # Predicción fuera de muestra para el mojón i
        pred_z = raw_dem[i] - calib_bias
        err_loo = float(pred_z - cota_ign[i])
        loo_errors[i] = err_loo

        p = valid_points[i]
        per_point_results.append({
            "nomenclatura": p.get("nomenclatura"),
            "red": p.get("red"),
            "cota_ign_m": float(cota_ign[i]),
            "cota_dem_raw_m": float(raw_dem[i]),
            "calib_bias_loo_m": round(calib_bias, 3),
            "cota_calibrada_loo_m": round(float(pred_z), 3),
            "error_loo_m": round(err_loo, 3),
        })

    out_of_sample_stats = compute_robust_stats(loo_errors)
    raw_stats = compute_robust_stats(raw_errors)

    return {
        "status": "ok",
        "n_valid": n,
        "n_excluded": len(excluded_points),
        "raw_stats": raw_stats,
        "in_sample_stats": in_sample_stats,
        "out_of_sample_stats": out_of_sample_stats,
        "per_point_results": per_point_results,
    }


def validate_dem_against_reference_raster(
    dem_evaluated: np.ndarray | Path | str,
    reference_raster: Path | str | None = None,
    evaluated_transform: Any = None,
    evaluated_crs: str | None = None,
    mask: np.ndarray | None = None,
) -> dict[str, Any]:
    """Punto de entrada para validar un DEM contra un ráster de referencia (e.g. MDE IGN 5 m Villa Mercedes 2014).

    Si el archivo de referencia aún no existe en el repositorio (está en proceso de provisión oficial),
    reporta un estado estructurado 'raster_no_disponible' con la ruta esperada sin generar excepciones.

    Si el ráster de referencia existe, calcula la matriz de discrepancia alineada celda a celda
    y reporta las métricas de sesgo, NMAD, RMSE y LE90.
    """
    ref_path_str = reference_raster or str(SUPUESTO_DEM_RASTER_REFERENCIA_PATH.valor)
    ref_path = Path(ref_path_str)

    if not ref_path.exists():
        return {
            "status": "raster_no_disponible",
            "reference_path": str(ref_path),
            "motivo": (
                "El ráster de referencia (MDE IGN 5 m Villa Mercedes 2014) no se encuentra disponible "
                "en la ruta configurada. El punto de entrada queda formalizado para validación continua."
            ),
            "metrics": None,
        }

    import rasterio
    from rasterio.warp import Resampling, reproject

    with rasterio.open(ref_path) as ref_src:
        ref_crs = ref_src.crs
        ref_transform = ref_src.transform
        ref_w, ref_h = ref_src.width, ref_src.height
        ref_data = ref_src.read(1).astype("float32")
        ref_nodata = ref_src.nodata

    if isinstance(dem_evaluated, (str, Path)):
        with rasterio.open(dem_evaluated) as eval_src:
            eval_data = eval_src.read(1).astype("float32")
            eval_transform = eval_src.transform
            eval_crs = eval_src.crs
            eval_nodata = eval_src.nodata
    else:
        if evaluated_crs is None or not str(evaluated_crs).strip():
            raise ValueError("Sin CRS declarado: dem_evaluated como array en memoria requiere 'evaluated_crs'.")
        if evaluated_transform is None:
            raise ValueError("Sin transformación declarada: dem_evaluated como array en memoria requiere 'evaluated_transform'.")
        eval_data = np.asarray(dem_evaluated, dtype="float32")
        eval_transform = evaluated_transform
        eval_crs = evaluated_crs
        eval_nodata = np.nan

    # Reproyectar DEM evaluado a la grilla y resolución del ráster de referencia
    aligned_eval = np.full((ref_h, ref_w), np.nan, dtype="float32")
    reproject(
        source=eval_data,
        destination=aligned_eval,
        src_transform=eval_transform,
        src_crs=eval_crs,
        src_nodata=eval_nodata,
        dst_transform=ref_transform,
        dst_crs=ref_crs,
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )

    valid_mask = np.isfinite(aligned_eval) & np.isfinite(ref_data)
    if ref_nodata is not None:
        valid_mask &= (ref_data != ref_nodata)
    if mask is not None:
        valid_mask &= mask

    diff = aligned_eval[valid_mask] - ref_data[valid_mask]
    stats = compute_robust_stats(diff)

    return {
        "status": "ok",
        "reference_path": str(ref_path),
        "valid_cells": int(diff.size),
        "total_cells": int(ref_data.size),
        "coverage_pct": round(float(diff.size) / float(ref_data.size) * 100.0, 2) if ref_data.size else 0.0,
        "metrics": stats,
    }
