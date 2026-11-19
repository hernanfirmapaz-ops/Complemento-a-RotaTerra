"""Geoprocesamiento del Visor 3D de hidrología (Complemento a RotaTerra).

Fase 0 + Fase 1 + Fase 2: lotes, DEM, calidad del DEM, cota, pendiente, hillshade, curvas de nivel,
acondicionamiento hidrológico selectivo, dirección D8, acumulación MFD/D8, red de drenaje
potencial, puntos de salida, subcuencas, eventos de lluvia (manual/CSV), modelo NRCS Curve Number
y distribución espacial de escorrentía potencial.
Todo cálculo de distancias, áreas y pendientes se hace en un CRS proyectado métrico (UTM),
nunca en grados (SDD §6.1).
"""

PROCESSING_VERSION = "fase2-nrcs-cn-escorrentia-v1"
