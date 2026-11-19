"""Geoprocesamiento del Visor 3D de hidrología (Complemento a RotaTerra).

Fases 0 a 5 completas: lotes (GeoJSON/KML/KMZ/Shapefile ZIP), DEM, calidad del DEM, cota,
pendiente, hillshade, curvas de nivel, acondicionamiento hidrológico selectivo, dirección D8,
acumulación MFD/D8, índices topográficos TWI y SPI, red de drenaje potencial, puntos de salida,
subcuencas, eventos de lluvia (manual/CSV), modelo NRCS Curve Number, tránsito temporal por
hietograma, solver hidrodinámico 2D de onda difusiva con Manning (water_depth_m y velocity_m_s)
e integración de ambientes hidro-agronómicos y transitabilidad para RotaTerra.
"""

PROCESSING_VERSION = "fase5-suite-completa-rotaterra-v1"
