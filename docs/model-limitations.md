# Limitaciones del modelo y advertencias técnicas (SDD §5.2, §6 y §11.2)

1. **Fase 0 — Solo análisis topográfico:** no se calcula dirección de flujo, acumulación, escorrentía, lámina de agua (`water_depth_m`) ni velocidad (`velocity_m_s`).
2. **Resolución espacial (regla de 30 m):** con un DEM de 30 m/píxel (Copernicus GLO-30 o MDE-Ar 30 m), un lote de 50 ha contiene apenas ~550 celdas y un lote de 200 ha ~2.200 celdas. Esa escala permite observar la pendiente general de la ladera, pero **jamás** surcos de labranza, cunetas, huellas, camellones ni microdepresiones.
3. **Modelo Digital de Superficie (DSM) vs. Terreno Desnudo (DTM):** los modelos radar/ópticos globales (Copernicus GLO-30, NASADEM) miden la superficie visible, por lo que cortinas forestales, montes, galpones o silos aparecen como elevaciones del terreno.
4. **No interpolación de vacíos (`nodata`):** las celdas sin dato se conservan como `NaN` tanto en las estadísticas como en la interpolación bilineal, la pendiente de Horn y la malla 3D (los triángulos que tocan un `NaN` no se renderizan).
5. **Exageración vertical:** cuando el usuario elige `2×`, `3×` o `5×` en la escena 3D, se muestra un aviso visible en pantalla; todos los valores numéricos (cota puntual, pendiente `%` / `°` y gráfico de perfil) se calculan siempre a escala real `1×` sobre el DEM en UTM.
