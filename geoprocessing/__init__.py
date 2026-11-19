"""Geoprocesamiento del Visor 3D de hidrología (Complemento a RotaTerra).

Fase 0: lotes, DEM, calidad del DEM, cota, pendiente, perfil y malla para la escena 3D.
Todo cálculo de distancias, áreas y pendientes se hace en un CRS proyectado métrico (UTM),
nunca en grados (SDD §6.1).
"""

PROCESSING_VERSION = "fase0-dem-v1"
