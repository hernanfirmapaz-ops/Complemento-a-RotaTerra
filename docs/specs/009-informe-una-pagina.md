# Spec 009 · Sección "Agua y suelo" para el informe de Rotaterra

**Proyecto:** `Complemento-a-RotaTerra`  
**Etapa:** 3 (Plan de Trabajo 20/11/2026, tarea 3.10)  
**Mejoras que cubre:** U2 (Informe de una página exportable e imprimible)  
**Dependencias:** Spec 003 (Resultados y comparador), Spec 006 (Riesgo de rinde por zona), Spec 008 (Ambientes topográficos), Spec 011 (Salida para Rotaterra).

> **Cambio de alcance (21/11/2026):** este módulo es parte de Rotaterra. En lugar de un PDF propio, genera una **sección "Agua y suelo"** (mapa + cifras + fuentes) que Rotaterra incluye en su informe. La sección también puede verse e imprimirse sola desde el paso Resultado, pero sin cifras económicas.

---

## 1. Objetivo y Caso de Uso ("La hoja que se lleva a la camioneta")

En el trabajo agronómico real, los informes de 20 páginas con gráficos complejos no se leen. El productor, el asesor y el contratista necesitan **una sola hoja A4**, clara, visual y ejecutiva, que responda en 10 segundos:
- ¿Cuánto se inundó o se puede inundar el lote?
- ¿Por dónde corre el agua y hacia dónde drena?
- ¿Cuánto rinde está en riesgo, en rango por zona? (la plata la calcula Rotaterra)
- ¿De dónde salieron los datos (fuente real y transparente)?

Esta spec define el contenido, diseño y generación automatizada del **Informe de Una Página (One-Page Report)** en formato PDF y HTML imprimible.

---

## 2. Estructura y Contenido de la Hoja A4

El informe está diseñado para caber estrictamente en **1 página A4** (sin desbordar a una segunda hoja bajo ninguna resolución de impresión):

```
+--------------------------------------------------------------------------+
| ROTATERRA · AGUA Y SUELO DEL LOTE                              [FECHA]   |
| Lote: Parcela 205 · Superficie: 443,3 ha · Villa Mercedes, San Luis       |
+--------------------------------------------------------------------------+
|                                                                          |
|   [ MAPA 2D EN ALTA RESOLUCIÓN ]                                        |
|   - Perímetro del lote y curvas de nivel (cada 0,5 o 1 m)                 |
|   - Manchas de anegamiento (> 2 cm) con código de color de días           |
|   - Red de drenaje y puntos de desborde hacia vecinos                    |
|   - Norte, escala gráfica y coordenadas                                  |
|                                                                          |
+--------------------------------------------------------------------------+
| 3 CIFRAS CLAVE DEL EVENTO                                                |
| [ 18,4 ha (4,1%) ]          [ 32.400 m³ ]         [ 20 – 45 % ]          |
| Área Anegada (>2cm)         Agua Almacenada       Merma de rinde en bajos|
+--------------------------------------------------------------------------+
| AMBIENTES TOPOGRÁFICOS                                                   |
| Loma: 142 ha (32%) · Media Loma: 245 ha (55%) · Bajo: 56 ha (13%)        |
| Manejo recomendado: siembra en contorno para reducir velocidad en ladera |
+--------------------------------------------------------------------------+
| FUENTES Y CONFIANZA TÉCNICA (Regla de honestidad)                        |
| • Relieve: Copernicus GLO-30 (30 m) · Confianza: Media (llanura 0,5%)    |
| • Suelo: SoilGrids 2.0 (Franco arenosa, Grupo A, Ksat 62 mm/día)         |
| • Lluvia: Tormenta de diseño 80 mm (15 min)                              |
| • Aviso: modelo de apoyo a la decisión, no reemplaza nivelación óptica.  |
+--------------------------------------------------------------------------+
```

---

## 3. Arquitectura Técnica de Generación

1. **Endpoints Backend:**
   - `GET /api/v1/fields/{id}/reports/agua-y-suelo` → HTML de la sección y datos en JSON, para que Rotaterra la incluya en su informe.
   - `GET /api/v1/fields/{id}/reports/agua-y-suelo.pdf` → la misma sección en una hoja A4, para imprimirla sola.
   - Genera una vista HTML5 semántica estilizada con CSS `@page { size: A4 portrait; margin: 12mm; }`.
   - Utiliza Playwright (ya integrado en la infraestructura de CI / calidad automática) para renderizar la página y exportar el PDF con fidelidad tipográfica vectorial y resolución de 300 DPI.
2. **Botón en Frontend:**
   - Ubicado exclusivamente en el **Paso 3 (Resultado)** de la interfaz minimalista ("Descargar informe en 1 hoja").
   - 0 emojis, diseño sobrio de línea.
3. **Caché y velocidad:**
   - La generación del PDF debe completarse en $< 2,5\text{ segundos}$ en servidor local.

---

## 4. Criterios de Aceptación Técnicos

1. **Restricción de 1 sola página:**
   - [ ] Test automatizado con Playwright que compila el PDF y verifica que `page_count == 1`.
2. **Contenido:**
   - [ ] Las 3 cifras clave coinciden exactamente con los resultados de la simulación 2D.
   - [ ] Fuentes de datos (DEM, Suelo, Lluvia) explícitamente declaradas sin textos engañosos.
   - [ ] Sin cifras económicas: la merma de rinde se informa en rango (%), y el cálculo en $ queda para Rotaterra.
3. **Impresión:**
   - [ ] El archivo PDF generado abre y se imprime en papel A4 sin recortes de márgenes ni fuentes rotas.
