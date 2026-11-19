"""Índices topográficos agro-hidrológicos derivados del DEM y la acumulación MFD (TWI y SPI).

- **TWI (Topographic Wetness Index, Beven & Kirkby 1979)**:
      TWI = ln(a / tan(beta))
  donde `a` es el área contribuyente específica por unidad de ancho de contorno (m²/m) y `beta` el
  ángulo de pendiente local. Valores altos indican zonas propensas a saturación edáfica y anegamiento.

- **SPI (Stream Power Index, Moore et al. 1991)**:
      SPI = a * tan(beta)
  Mide el poder erosivo potencial del flujo superficial concentrado.

Nota (SDD §2.2): son índices topográficos preliminares; no representan pérdidas de suelo en t/ha/año
validadas (RUSLE/WEPP).
"""

from __future__ import annotations

import numpy as np


def compute_twi_and_spi(
    mfd_area_m2: np.ndarray,
    slope_pct: np.ndarray,
    pixel_size_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Calcula las grillas `twi` y `spi` (float32, NaN donde falta cota o pendiente)."""
    valid = np.isfinite(mfd_area_m2) & np.isfinite(slope_pct)
    # Área contribuyente específica a (m² por metro de contorno)
    specific_a = np.where(valid, np.maximum(pixel_size_m, mfd_area_m2 / float(pixel_size_m)), np.nan)
    # Evitar división por cero en celdas planas: pendiente mínima equivalente a 0,1 % (tan(beta) = 0.001)
    tan_beta = np.where(valid, np.maximum(0.001, slope_pct / 100.0), np.nan)

    with np.errstate(invalid="ignore", divide="ignore"):
        twi = np.log(specific_a / tan_beta)
        spi = specific_a * tan_beta

    return twi.astype("float32"), spi.astype("float32")
