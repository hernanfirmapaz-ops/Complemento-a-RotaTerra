# Spec 009 · Informe de Una Página (Síntesis A4 para Campo)

**Proyecto:** `Complemento-a-RotaTerra`  
**Etapa:** 3 (Plan de Trabajo 20/11/2026, tarea 3.10)  
**Mejoras que cubre:** U2 (Informe de una página exportable e imprimible)  
**Dependencias:** Spec 003 (Resultados y comparador), Spec 006 (Riesgo de rinde y económico), Spec 008 (Ambientes topográficos).

---

## 1. Objetivo y Caso de Uso ("La hoja que se lleva a la camioneta")

En el trabajo agronómico real, los informes de 20 páginas con gráficos complejos no se leen. El productor, el asesor y el contratista necesitan **una sola hoja A4**, clara, visual y ejecutiva, que responda en 10 segundos:
- ¿Cuánto se inundó o se puede inundar el lote?
- ¿Por dónde corre el agua y hacia dónde drena?
- ¿Cuánta plata o rinde está en riesgo?
- ¿De dónde salieron los datos (fuente real y transparente)?

Esta spec define el contenido, diseño y generación automatizada del **Informe de Una Página (One-Page Report)** en formato PDF y HTML imprimible.

---

## 2. Estructura y Contenido de la Hoja A4

El informe está diseñado para caber estrictamente en **1 página A4** (sin desbordar a una segunda hoja bajo ninguna resolución de impresión):

```
+--------------------------------------------------------------------------+
| ROTATERRA 3D · INFORME AGRO-HIDROLÓGICO                        [FECHA]   |
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
| [ 18,4 ha (4,1%) ]          [ 32.400 m³ ]         [ USD 4.200 – 7.800 ]  |
| Área Anegada (>2cm)         Agua Almacenada       Pérdida Económica Est. |
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

1. **Endpoint Backend:**
   - `GET /api/v1/fields/{id}/reports/summary-pdf`
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
   - [ ] Pérdida económica informada en rango (nunca valor puntual).
3. **Impresión:**
   - [ ] El archivo PDF generado abre y se imprime en papel A4 sin recortes de márgenes ni fuentes rotas.
