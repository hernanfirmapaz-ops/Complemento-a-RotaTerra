# Plan de trabajo · RotaTerra 3D

**Fecha:** 20/11/2026 · **Responsable:** Hernán Firmapaz · **Ejecución:** Antigravity (coordinador + 4 especialistas)
**Base:** `mejoras-y-competencia-rotaterra.md`, spec 001 (escurrimiento) y SDD 002 (rediseño)

---

## 1. Resumen

| Etapa | Período estimado | Objetivo | Specs |
|---|---|---|---|
| 0 · Correcciones | 20/11 – 29/11 | App honesta y sin lotes de ejemplo | Pedido 20/11 |
| 1 · Rediseño | 30/11 – 20/12 | Interfaz minimalista | SDD 002 |
| 2 · Ahora | 21/12 – 17/01 | Simple, confiable y comparativa | 003 |
| 3 · Próxima | 18/01 – 28/02 | "Si hago esta zanja, salvo X ha" | 004 · 005 · 006 · 007 |
| 4 · Después | 01/03 – 30/04 | La app aprende del lote | 008 · 009 |
| 5 · Más adelante | 01/05 – 31/07 | Precisión profesional | 010 · 011 · 012 · 013 |
| 6 · Futuro | Sin fecha | Integraciones con plataformas | 014 |

Las fechas suponen trabajo de tiempo parcial y una revisión tuya por semana. Entre el 24/12 y el 06/01 se estima la mitad de ritmo.

---

## 2. Reglas del plan

1. **Spec primero.** Cada etapa arranca con su spec aprobada por vos. Sin spec, no hay código.
2. **Una rama y un PR por tarea.** Nada se mergea sin tu aprobación.
3. **Nada en la primera pantalla.** Toda función nueva entra en el flujo Lote → Lluvia → Resultado o en "Más análisis".
4. **Nunca inventar un valor.** Rangos en lugar de cifras únicas cuando hay incertidumbre; fuente siempre visible.
5. **Definición de terminado:** `pytest` y `npm run build` en verde, sin tests que usen internet, capturas a 390 y 1440 px y criterios de la spec tildados con evidencia.
6. **Una etapa no empieza** hasta que la anterior tenga sus PR aprobados, salvo tareas marcadas como paralelas.

---

## 3. Specs nuevas

| Spec | Nombre | Mejoras que cubre | Etapa |
|---|---|---|---|
| 003 | Escenarios, confianza y entorno del lote | U3 · C2 · S4 | 2 |
| 004 | Impacto del encharcamiento en el rinde | R1 · R2 | 3 |
| 005 | Editar el terreno y dirección de siembra | S2 · S1 · S3 | 3 |
| 006 | Posición en el paisaje y ambientes exportables | R5 · R6 · I2 | 3 |
| 007 | Informe de una página | U2 | 3 |
| 008 | Memoria del lote | R3 · C3 | 4 |
| 009 | Historial automático de lluvias reales | R4 · I1 | 4 |
| 010 | Napa freática (modo estacional) | S5 | 5 |
| 011 | Relieve propio: dron y monitor de rinde | S6 | 5 |
| 012 | Validación del motor 2D | C4 | 5 |
| 013 | Lotes guardados y uso sin señal | U4 · U5 · U6 | 5 |
| 014 | Importar lotes de plataformas | I3 | 6 |

---

## 4. Detalle por etapa

### Etapa 0 · Correcciones (en curso)

| ID | Tarea | Agente | Rama | Depende de | Estado | Criterio de aceptación |
|---|---|---|---|---|---|---|
| 0.1 | Fuentes de lluvia reales (sin SMN/CONAE/SAOCOM) | experto-datos + backend + frontend | `fix/atribucion-fuentes-lluvia` | — | **Hecho** (PR listo) | `grep` sin atribuciones falsas; test de fuente |
| 0.2 | Test de balance hídrico con NASA POWER simulado | backend | `fix/test-balance-hidrico-offline` | — | **En curso** | 160/160 tests sin conexión |
| 0.3 | Mensaje claro sin conexión (sin relieve inventado) | backend | `fix/relieve-sin-conexion` | — | Pendiente | Sin 422 genérico |
| 0.4 | Eliminar lotes de ejemplo de la app; mover a `tests/fixtures/lotes/` | backend + frontend | `chore/quitar-lotes-ejemplo` | — | Pendiente | `grep "ejemplo\|sample"` sin resultados de interfaz |
| 0.5 | Borrar ramas sobrantes | coordinador | — | — | Pendiente | Solo `main` |

**Punto de control:** revisás los PR. Yo puedo verificarlos antes del merge.

### Etapa 1 · Rediseño (SDD 002)

| ID | Tarea | Agente | Rama | Depende de | Estado | Criterio de aceptación |
|---|---|---|---|---|---|---|
| 1.1 | Tokens + componentes `ui/` | frontend | `feat/ui-sistema-minimalista` | Etapa 0 | Pendiente | Página de muestra de componentes |
| 1.2 | Landing (base: referencia aprobada) | frontend | `feat/landing-minimalista` | 1.1 | Pendiente | Lighthouse accesibilidad ≥ 95 |
| 1.3 | Flujo Lote → Lluvia → Resultado (escritorio) | frontend | `feat/app-flujo-3-pasos` | 1.1 | Pendiente | ≤ 6 botones en la primera pantalla |
| 1.4 | Celular: hoja inferior y gestos | frontend | `feat/app-celular` | 1.3 | Pendiente | Sin desborde a 360 px |
| 1.5 | Visor: paleta de datos y leyendas | frontend | `feat/visor-estetica` | 1.3 | Pendiente | 0 emojis, 0 degradados fuera del visor |
| 1.6 | Limpieza de CSS y componentes viejos | frontend + coordinador | `chore/ui-limpieza` | 1.2–1.5 | Pendiente | `styles.css` < 600 líneas; JS inicial < 250 kB |

**Punto de control:** prueba con 3 personas sin experiencia técnica, con tiempos anotados.

### Etapa 2 · Ahora (spec 003)

| ID | Tarea | Agente | Rama | Depende de | Estado | Criterio de aceptación |
|---|---|---|---|---|---|---|
| 2.1 | Escribir spec 003 | coordinador | `docs/spec-003` | Etapa 1 | Pendiente | Aprobada por Hernán |
| 2.2 | **Entorno del lote:** margen configurable de 300–500 m, menor resolución fuera del lote | experto-datos + hidrólogo | `feat/entorno-lote` | 2.1 | Pendiente | Agua que entra desde afuera visible y cuantificada en m³ |
| 2.3 | **Indicador de confianza** alto/medio/bajo según relieve, suelo y lluvia | hidrólogo + frontend | `feat/indicador-confianza` | 2.1 | Pendiente | Visible en cada resultado, con su motivo |
| 2.4 | **Comparar escenarios** lado a lado (manejo o lluvia) | backend + frontend | `feat/comparar-escenarios` | 2.1 | Pendiente | 2 escenarios en pantalla dividida; diferencias en ha, % y t/ha |

### Etapa 3 · Próxima (specs 004–007)

| ID | Tarea | Agente | Rama | Depende de | Estado | Criterio de aceptación |
|---|---|---|---|---|---|---|
| 3.1 | Escribir specs 004–007 | coordinador | `docs/specs-004-007` | Etapa 2 | Pendiente | Aprobadas |
| 3.2 | **Días de encharcamiento** por zona (vaciado por infiltración y evaporación) | hidrólogo | `feat/dias-encharcamiento` | 3.1 | Pendiente | Mapa de días con balance de masa verificado |
| 3.3 | **Riesgo de rinde** por cultivo según días (rangos, fuente visible) | hidrólogo + frontend | `feat/riesgo-rinde` | 3.2 | Pendiente | Rango de pérdida por zona; umbrales editables |
| 3.4 | **Impacto económico** (ha × rinde × precio, editable) | backend + frontend | `feat/impacto-economico` | 3.3 | Pendiente | Resultado en rango, nunca cifra única |
| 3.5 | **Editar terreno:** zanja, terraplén, camino, alcantarilla | hidrólogo + frontend | `feat/editar-terreno` | 3.1 | Pendiente | Dibujar, simular de nuevo y comparar con 2.4 |
| 3.6 | **Dirección de siembra** que condiciona el flujo | hidrólogo | `feat/direccion-siembra` | 3.5 | Pendiente | Diferencia visible entre surcos a favor y en contra de la pendiente |
| 3.7 | **Puntos de desborde** de cada bajo | hidrólogo + frontend | `feat/puntos-desborde` | 3.1 | Pendiente | Punto y destino del rebalse en el visor |
| 3.8 | **Posición en el paisaje** (loma, media loma, bajo) con hectáreas | hidrólogo | `feat/posicion-paisaje` | 3.1 | Pendiente | Suma de superficies = superficie del lote |
| 3.9 | **Exportar** ambientes, flujo y encharcamiento (Shapefile, GeoJSON, CSV) | backend | `feat/exportar-capas` | 3.8 | Pendiente | Archivos abren en QGIS sin errores |
| 3.10 | **Informe de una página** (PDF) | backend + frontend | `feat/informe-pdf` | 3.3, 3.8 | Pendiente | Una hoja A4 con mapa, 3 cifras, fuentes y límites |

Paralelas: 3.2–3.4, 3.5–3.7 y 3.8–3.9 pueden avanzar al mismo tiempo.

**Punto de control:** demo con un productor real de la zona, usando su lote.

### Etapa 4 · Después (specs 008–009)

| ID | Tarea | Agente | Rama | Depende de | Estado | Criterio de aceptación |
|---|---|---|---|---|---|---|
| 4.1 | Escribir specs 008–009 | coordinador | `docs/specs-008-009` | Etapa 3 | Pendiente | Aprobadas |
| 4.2 | **Usar la API de N4-4-1.2** para clima, lluvia, humedad y NDVI | experto-datos + backend | `feat/api-n4` | 4.1 | Pendiente | Conectores propios duplicados eliminados |
| 4.3 | **Memoria del lote:** frecuencia de anegamiento 1985–hoy (Landsat, HLS, OPERA DSWx) | experto-datos | `feat/memoria-lote` | 4.1 | Pendiente | Mapa de frecuencia con años y fuente por píxel |
| 4.4 | **Validación contra la memoria:** índice F entre simulación y anegamientos reales | hidrólogo | `feat/validacion-memoria` | 4.3 | Pendiente | Índice F publicado para 3 eventos |
| 4.5 | **Historial automático:** cada lluvia de IMERG > 20 mm se simula y queda registrada | backend + experto-datos | `feat/historial-lluvias` | 4.2 | Pendiente | Lista cronológica de eventos con resultado |

### Etapa 5 · Más adelante (specs 010–013)

| ID | Tarea | Agente | Rama | Depende de | Estado | Criterio de aceptación |
|---|---|---|---|---|---|---|
| 5.1 | **Napa freática:** modo estacional con freatímetro del productor | hidrólogo | `feat/napa-estacional` | spec 010 | Pendiente | Escenarios húmedo/seco; días anegados por napa |
| 5.2 | **Relieve propio:** subir GeoTIFF de dron o puntos del monitor de rinde | experto-datos + backend | `feat/relieve-propio` | spec 011 | Pendiente | Datum y precisión declarados; reemplaza al satelital |
| 5.3 | **Comparación del motor 2D con Landlab** | hidrólogo | `feat/benchmark-landlab` | spec 012 | Pendiente | Diferencia de área anegada < 15% |
| 5.4 | **Lotes guardados** en el navegador | frontend | `feat/lotes-guardados` | spec 013 | Pendiente | Volver a un lote sin dibujarlo |
| 5.5 | **Uso sin señal** (PWA) | frontend | `feat/pwa` | 5.4 | Pendiente | Lote guardado abre sin conexión |
| 5.6 | **Primera visita guiada** de 3 pasos | frontend | `feat/visita-guiada` | spec 013 | Pendiente | Se muestra una sola vez |

### Etapa 6 · Futuro (spec 014)

| ID | Tarea | Agente | Criterio |
|---|---|---|---|
| 6.1 | Importar lotes desde John Deere Operations Center, Auravant o FieldView | backend | Lote importado sin dibujarlo a mano |
| 6.2 | Exportar ISOXML para maquinaria | backend | Archivo aceptado por un monitor de siembra |

---

## 5. Puntos de control (tus decisiones)

| Cuándo | Qué decidís |
|---|---|
| Fin etapa 0 | Merge de correcciones |
| Inicio etapa 1 | Color de acento final (verde o negro) |
| Fin etapa 1 | Aprobación del rediseño tras la prueba con 3 personas |
| Inicio etapa 3 | Cultivos y umbrales de días para el riesgo de rinde |
| Fin etapa 3 | Demo con un productor: seguir o ajustar prioridades |
| Inicio etapa 4 | Confirmar la integración con N4-4-1.2 |
| Inicio etapa 5 | Si la napa es prioridad (requiere datos de freatímetro) |

---

## 6. Indicadores de avance

| Indicador | Meta |
|---|---|
| Tests | 100% en verde en cada PR |
| Tiempo de abrir a ver el resultado (usuario nuevo) | < 60 s |
| Botones en la primera pantalla | ≤ 6 |
| JS inicial | < 250 kB comprimido |
| Resultados con fuente e indicador de confianza | 100% |
| Validación contra anegamientos reales | Índice F publicado (etapa 4) |

---

## 7. Riesgos del plan

| Riesgo | Mitigación |
|---|---|
| Funciones nuevas vuelven a sobrecargar la interfaz | Regla 3; el coordinador rechaza el PR si agrega botones a la primera pantalla |
| Antigravity vuelve a subir ramas viejas o mezcla tareas | Rama nueva desde `main` actualizado por tarea; revisión semanal de ramas |
| Etapas largas sin revisión | Un PR chico por tarea; revisión semanal |
| Fechas de fin de año | Ritmo reducido entre el 24/12 y el 06/01 |
| Datos externos caídos (NASA, Copernicus) | Mensajes claros, sin datos inventados; tests sin internet |
