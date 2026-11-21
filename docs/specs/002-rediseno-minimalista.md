# SDD 002 · Rediseño minimalista de RotaTerra 3D

| Campo | Valor |
|---|---|
| **Proyecto** | Complemento a RotaTerra (`hernanfirmapaz-ops/Complemento-a-RotaTerra`) |
| **Área** | `apps/web/` (+ landing nueva) |
| **Estado** | Propuesta, pendiente de aprobación de Hernán |
| **Fecha** | 20/11/2026 |
| **Responsable de aprobación** | Hernán Firmapaz |
| **Agente líder** | `frontend-3d`, con revisión del `coordinador` |
| **Depende de** | Pedido del 20/11 (tareas 1, 3 y 4). **Reemplaza a la tarea 2** (celular): no hacer ambas |

---

## 1. Prompt base completado

El prompt original pedía una sola página HTML minimalista. Acá está completado para RotaTerra y extendido para que valga como sistema de diseño de toda la app, no solo de una landing.

> Actuá como un diseñador UI/UX senior y desarrollador frontend experto en diseño web minimalista moderno. Creá el código completo y funcional de una página web minimalista en un único archivo HTML (con CSS moderno integrado, usando variables CSS, Flexbox y CSS Grid).
>
> **1. Contexto del proyecto**
> - **Objetivo del sitio:** landing page de una app web agrícola que simula, sobre el relieve real de un lote, por dónde corre el agua de lluvia, dónde se encharca y cuánto suelo se pierde, para decidir rotaciones y coberturas.
> - **Nombre:** RotaTerra
> - **Propuesta de valor (Hero):** "Mirá cómo corre el agua en tu campo antes de sembrar."
> - **Subtítulo:** "Dibujá tu lote, simulá una lluvia y descubrí dónde se encharca, por dónde escurre y cuánto suelo perdés. Con relieve satelital y datos de la NASA."
> - **Secciones:** Inicio (hero con imagen del lote 3D) · Cómo funciona (3 pasos) · Qué resuelve (4 herramientas) · Datos (fuentes y límites) · Cierre con CTA "Probar con un lote de ejemplo".
> - **Navegación (máx. 4):** Cómo funciona · Herramientas · Datos · **Abrir simulador** (CTA).
>
> **2. Directrices de diseño:** las del prompt original, con estos valores: fondo `#FFFFFF`, superficies `#FAFAFA`, texto `#111111`, secundario `#666666`, bordes `#EAEAEA`, **único acento verde campo `#1E6B47`** (solo CTA y hover). Tipografía **Inter**. Sin emojis: íconos de línea de 1,5 px.
>
> **3. Requisitos técnicos:** los del prompt original, más soporte de `prefers-reduced-motion` y modo oscuro opcional con la misma lógica monocromática.

**Por qué verde y no azul:** el azul queda reservado para **el agua dentro del visor 3D**. Si el CTA también fuera azul, el usuario confundiría "botón" con "agua". El verde conecta con el campo sin competir con los datos.

---

## 2. Objetivo

Pasar de una interfaz tipo "tablero de control" a una experiencia **sobria, calma y enfocada**, en la línea de las páginas de producto de Apple: una idea por pantalla, el lote 3D como protagonista y todo lo demás escondido hasta que hace falta.

**Meta medible:** un productor sin experiencia técnica tiene que poder ir de "abrir" a "ver dónde se encharca su lote" en **3 decisiones o menos** y en menos de 60 segundos con un lote de ejemplo.

## 3. Alcance

| Incluye | Excluye |
|---|---|
| Landing nueva (`/`) en un solo HTML, según el prompt | Cambios en la física, la API o los datos |
| Rediseño completo del simulador (`/app`) | Nuevas herramientas o funciones |
| Sistema de diseño (tokens, componentes, íconos) | Marca/logotipo definitivo (se usa logotipo tipográfico) |
| Versión para el celular (mobile-first) | App nativa |
| Textos (microcopy) y estados vacíos, de carga y de error | Traducción a otros idiomas |

---

## 4. Diagnóstico de la interfaz actual

Medido sobre `main` del 20/11/2026.

| Indicador | Hoy | Objetivo |
|---|---|---|
| Colores distintos en `styles.css` | **66** | ≤ 8 tokens + paleta de datos del visor |
| Degradados (`gradient`) | **19** | 0 fuera del visor |
| Sombras (`box-shadow`) | **13** | 0 (solo un borde de 1 px) |
| Animaciones (`@keyframes`) | **6** | 1 (indicador de carga) |
| Emojis como íconos | **~70** | 0 |
| Líneas de `App.tsx` | **2.365** | < 400 (repartidas en componentes) |
| Líneas de `styles.css` | **2.171** | < 600 |
| Columnas en escritorio | 3 paneles + visor | 1 visor + 1 panel contextual |
| Botones visibles en la primera pantalla | **~35** | ≤ 6 |
| Acciones primarias simultáneas | Varias (naranja, verde, azul) | **1 por vista** |
| Selector de exageración vertical | 5 opciones siempre visibles | 1 control deslizante dentro de "Ajustes de vista" |
| Pestañas de capas en el visor | 7 chips + 4 controles flotantes | 3 capas principales + menú "Más" |
| Herramientas agronómicas | 9 botones en grilla | Lista de 4 temas, el resto en "Más análisis" |
| Uso en celular | Roto (columnas cortadas, títulos pisados) | Una columna, visor arriba, hoja inferior |

### Problemas principales

1. **Todo compite a la vez.** Paso 1, Paso 2, Paso 3, encabezado y pie se muestran juntos, con colores distintos para cada uno.
2. **Ruido decorativo.** Emojis, insignias ("Red SMN & CONAE Online"), píldoras de colores, degradados y sombras.
3. **Repetición.** "Dibujar mi lote" aparece 3 veces (encabezado, Paso 1 y chips del visor).
4. **Textos largos dentro de botones** ("Ejemplo 2: Lote Agrícola #205 (199 ha · Llanura ondulada)").
5. **Jerga visible** antes de tiempo (TWI, SPI, USLE, AMC, NDVI) en la primera pantalla.
6. **Indicadores sin contexto** ("Comportamiento Hidrológico Estable") que aparecen antes de cargar un lote.

---

## 5. Principios de diseño

| # | Principio | Cómo se aplica |
|---|---|---|
| P1 | **Una cosa por vez** | Cada paso ocupa el panel solo; el siguiente aparece cuando el anterior terminó |
| P2 | **El lote es el protagonista** | El visor ocupa ≥ 65% de la pantalla en escritorio y ≥ 55% del alto en el celular |
| P3 | **Mostrar progresivamente** | Lo técnico (TWI, CN, Manning, datum) vive en "Detalles" plegables |
| P4 | **Un solo acento** | Verde `#1E6B47` solo en la acción principal de cada vista |
| P5 | **Silencio visual** | Sin sombras, degradados ni emojis; separación con espacio y líneas de 1 px |
| P6 | **Palabras de campo** | "Dónde se encharca" antes que "Profundidad máxima"; el término técnico va como subtítulo |
| P7 | **Honestidad visible** | Fuente, resolución y límites de cada dato, en gris, siempre a un toque |

---

## 6. Sistema de diseño

### 6.1 Color

| Token | Valor | Uso |
|---|---|---|
| `--bg` | `#FFFFFF` | Fondo principal |
| `--surface` | `#FAFAFA` | Panel lateral, hojas, campos de texto |
| `--line` | `#EAEAEA` | Bordes y divisores (1 px) |
| `--ink` | `#111111` | Texto principal |
| `--ink-2` | `#666666` | Texto secundario, etiquetas, fuentes |
| `--ink-3` | `#999999` | Deshabilitado, marcadores de posición |
| `--accent` | `#1E6B47` | CTA principal, foco, selección |
| `--accent-hover` | `#16573A` | Hover del CTA |
| `--danger` | `#B42318` | Solo errores |

**Modo oscuro (opcional, fase 4):** `--bg #0B0B0C`, `--surface #151517`, `--line #26262A`, `--ink #F5F5F7`, `--ink-2 #A1A1A6`, `--accent #3FA472`.

**Paleta de datos (solo dentro del visor y de los gráficos), cartográfica y apta para daltonismo:**

| Capa | Escala |
|---|---|
| Agua (profundidad) | Azul secuencial: `#DCEBFA` → `#2B7BD6` → `#0B3D7A` |
| Relieve | Tierra neutra: `#F2EEE6` → `#A89F8E` → `#5C5446` |
| Pérdida de suelo | Secuencial ámbar-rojo: `#FDF1D8` → `#E08A2E` → `#9E2A12` |
| Vigor (NDVI) | Secuencial verde: `#EEF5E9` → `#7FB069` → `#2E6B2F` |

### 6.2 Tipografía

**Fuente:** Inter (Google Fonts), pesos 400, 500 y 600. Respaldo: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`. Cifras tabulares (`font-variant-numeric: tabular-nums`) en todo número.

| Token | Tamaño (móvil → escritorio) | Peso | Interlineado | Uso |
|---|---|---|---|---|
| `--t-display` | `clamp(40px, 7vw, 80px)` | 600 | 1,05 | Hero de la landing |
| `--t-h1` | `clamp(28px, 4vw, 48px)` | 600 | 1,1 | Títulos de sección |
| `--t-h2` | `22px` | 600 | 1,2 | Título del panel |
| `--t-metric` | `clamp(32px, 4vw, 44px)` | 500 | 1,0 | Cifra principal del resultado |
| `--t-body` | `17px` | 400 | 1,55 | Texto (máx. 65ch) |
| `--t-small` | `14px` | 400 | 1,45 | Etiquetas, fuentes, ayudas |

Espaciado de letras: `-0,02em` en display y h1; normal en el resto. Sin mayúsculas sostenidas.

### 6.3 Espaciado, forma y movimiento

| Token | Valor |
|---|---|
| Unidad base | 8 px (`--s1 8` · `--s2 16` · `--s3 24` · `--s4 32` · `--s6 48` · `--s8 64`) |
| Separación entre secciones (landing) | 96 px en el celular, 120 px en escritorio |
| Padding del panel | 32 px en escritorio, 24 px en el celular |
| Ancho máximo de contenido | 1120 px (landing); panel lateral 380 px |
| Radios | 12 px en tarjetas y hojas, 999 px en botones |
| Bordes | 1 px `--line`; nunca más gruesos |
| Sombras | Ninguna. Excepción: la hoja inferior del celular puede usar `0 -1px 0 var(--line)` |
| Transiciones | `0.2s ease` en color, fondo, borde y opacidad. Ninguna en tamaño o posición del layout |
| Movimiento reducido | Con `prefers-reduced-motion`: sin animación de lluvia ni rotación automática |

### 6.4 Íconos

- Línea de 1,5 px, 20 px, color `currentColor`, sin rellenos (estilo Lucide/SF Symbols).
- SVG en línea, sin librería externa (o `lucide-react` con importación individual, si se aprueba).
- **Prohibidos los emojis** en la interfaz.
- Íconos solo cuando ayudan a reconocer; nunca decorativos.

### 6.5 Componentes base

| Componente | Especificación |
|---|---|
| **Botón primario** | Fondo `--accent`, texto blanco 15 px/500, alto 44 px, padding 0 22 px, radio 999 px. Hover `--accent-hover`. **Uno solo por vista** |
| **Botón secundario** | Fondo transparente, borde 1 px `--line`, texto `--ink`. Hover: fondo `--surface` |
| **Botón de texto** | Solo texto `--accent` con flecha `→`; hover con subrayado |
| **Control segmentado** | Fondo `--surface`, opción activa con fondo blanco y borde `--line`; máx. 4 opciones |
| **Lista de opciones** | Filas de 56 px con título y subtítulo gris, divisor de 1 px, chevron a la derecha |
| **Métrica** | Número `--t-metric` + unidad `--t-small` gris + etiqueta debajo |
| **Detalles** | `<details>` nativo: "Ver detalles técnicos" con chevron que rota 90° |
| **Hoja inferior (móvil)** | 3 alturas: plegada (72 px), media (50%) y completa (90%); tirador de 36 × 4 px |
| **Leyenda del visor** | Barra de color de 120 × 6 px, valores mín./máx. y unidad; fondo blanco con 90% de opacidad |
| **Nota de fuente** | 14 px `--ink-2`: "Fuente: Copernicus GLO-30 · 30 m · error ±2 m" |
| **Aviso** | Línea de 1 px a la izquierda en `--ink-2`, texto 14 px; sin cajas de color |
| **Indicador de carga** | Barra lineal fina de 2 px en `--accent` con texto del paso ("Descargando relieve…"). Reemplaza al overlay animado |

---

## 7. Arquitectura de información

### 7.1 Mapa del sitio

```
/            Landing (un HTML, según el prompt)
/app         Simulador
  ├─ Lote       Elegir ejemplo · Dibujar · Subir archivo
  ├─ Lluvia     Intensidad · Día real · Estado del suelo · Manejo
  └─ Resultado  Resumen · Agua · Suelo · Más análisis
```

### 7.2 Flujo principal (3 decisiones)

| # | El usuario | La interfaz muestra |
|---|---|---|
| 1 | Elige "Lote de llanura (199 ha)" | El lote aparece en 3D; el panel pasa a "Lluvia" |
| 2 | Elige "Fuerte · 80 mm" | El valor por defecto ya está marcado; el CTA dice "Simular lluvia" |
| 3 | Toca "Simular lluvia" | Animación de agua en el visor; el panel pasa a "Resultado" con 3 cifras |

Todo lo demás (día real, estado del suelo, cobertura, exageración del relieve, capas técnicas, las 8 herramientas) queda accesible pero **plegado**.

### 7.3 Qué se agrupa, se esconde o se elimina

| Elemento actual | Destino |
|---|---|
| Insignia "Red SMN & CONAE Online" | **Eliminar** (además es una atribución incorrecta; ver pedido del 20/11, tarea 1) |
| Título largo del encabezado | Logotipo "RotaTerra" + nombre del lote actual |
| Pestañas "Vista Maqueta 3D / Mapa GIS" | Control segmentado "3D · Mapa", dentro del visor (esquina superior derecha) |
| "Dibujar mi lote" ×3 | Una sola vez, en el paso Lote |
| Selector de relieve (5 opciones) | Control deslizante en "Ajustes de vista" (ícono de engranaje en el visor) |
| 7 chips de capas | 3 capas visibles: **Agua · Relieve · Suelo**; el resto (NDVI, lomas y bajos, TWI/SPI) en "Más capas" |
| 4 controles flotantes (centrar, 2D, zoom, norte) | Un grupo vertical de 3 íconos (centrar, 2D/3D, norte); el zoom va con gestos y rueda |
| Ayuda "Arrastrá con botón izquierdo…" | Aparece una sola vez, 4 s, al cargar el primer lote |
| Indicador "Comportamiento Hidrológico Estable" antes de cargar | **Eliminar**; solo aparece en Resultado |
| Frase "ANTES DE SEMBRAR O INVERTIR…" | Va a la landing |
| 9 botones de herramientas | Resultado → "Resumen, Agua, Suelo" + "Más análisis" (siembra, rotación, heladas, vigor, terrazas) |
| Overlay de carga animado (cultivos, satélites, tips) | Barra de 2 px + texto del paso |
| Pie de página con fuentes | "Fuentes" plegable dentro de Resultado, más una nota fija de 14 px |

---

## 8. Pantallas

### 8.1 Landing (`/`)

| Sección | Contenido | Layout |
|---|---|---|
| **Navegación** | "RotaTerra" a la izquierda · Cómo funciona · Herramientas · Datos · [Abrir simulador] | Fija, 64 px, fondo blanco con 90% de opacidad y desenfoque; línea inferior 1 px al hacer scroll |
| **Hero** | Display: "Mirá cómo corre el agua en tu campo antes de sembrar." · Subtítulo (65ch) · CTA "Probar con un lote de ejemplo" · Botón de texto "Cómo funciona →" · Imagen grande del lote 3D con agua (captura real del visor) | Centrado, 120 px arriba; imagen a todo el ancho del contenido con radio de 12 px |
| **Cómo funciona** | 1 · Dibujá tu lote — "Marcá las esquinas en el mapa o subí un KML." · 2 · Elegí una lluvia — "Una tormenta de diseño o un día real." · 3 · Mirá el resultado — "Dónde se encharca, por dónde escurre y cuánto suelo se va." | 3 columnas en escritorio, 1 en el celular; número en `--ink-2`, sin tarjetas |
| **Qué resuelve** | Encharcamiento · Erosión · Rotación · Heladas, cada uno con una línea de explicación y un ícono de línea | Grilla 2 × 2, divisores de 1 px |
| **Datos** | "Relieve satelital de 30 m, lluvia y clima de la NASA y suelos del INTA." + lista de fuentes con resolución + aviso: "Los resultados son orientativos: el relieve satelital tiene errores de 1 a 3 m." | Texto a 65ch, tabla mínima de 3 columnas |
| **Cierre** | h1: "Tu próximo lote empieza con una lluvia simulada." + CTA | Centrado, fondo `--surface` |
| **Pie** | "RotaTerra · Villa Mercedes, San Luis · Proyecto personal de Hernán Firmapaz" + enlace al repositorio | 14 px `--ink-2` |

### 8.2 Simulador en escritorio (≥ 1024 px)

```
┌──────────────────────────────────────────────────────────────┐
│ RotaTerra   Lote de llanura · 199 ha              [3D | Mapa]│  64 px
├───────────────┬──────────────────────────────────────────────┤
│ Lote ✓        │                                              │
│ Lluvia ●      │                                              │
│ Resultado     │              VISOR 3D (protagonista)         │
│ ───────────── │                                         [◎]  │
│ ¿Cuánto llueve?│                                         [2D] │
│ (o)30 (•)80 (o)130│                                     [N]  │
│               │                                              │
│ Más opciones ▸│   ▁▁▁▁▁ Agua 0–45 cm                        │
│               │                                              │
│ [Simular lluvia]│  Agua · Relieve · Suelo · Más ▾            │
│ Fuente: …     │                                              │
└───────────────┴──────────────────────────────────────────────┘
   380 px                    resto (≥ 65%)
```

- Panel izquierdo de 380 px: indicador de pasos (texto con ✓ / ● / gris, sin insignias) + el contenido del paso activo.
- Visor: fondo `#F5F5F4`, sin marco; controles de 36 px con fondo blanco y borde de 1 px.

### 8.3 Simulador en el celular (< 768 px)

```
┌──────────────────────┐
│ RotaTerra    [3D|Mapa]│  56 px
├──────────────────────┤
│                      │
│     VISOR 3D         │  ≥ 55% del alto
│                [◎]   │
├──────── ▬ ───────────┤  hoja inferior
│ Lluvia               │
│ (o)30 (•)80 (o)130   │
│ [  Simular lluvia  ] │
└──────────────────────┘
```

- Hoja inferior con 3 alturas; el CTA queda siempre visible abajo.
- Capas: botón "Capas" en el visor que abre una lista en la hoja.
- Sin desplazamiento horizontal a 360 px.

### 8.4 Contenido de cada paso

**Paso Lote**
- Título: "Elegí tu lote"
- Lista: "Lote de llanura" · *199 ha · Villa Mercedes* / "Lote de piedemonte" · *223 ha · relieve marcado* / "Dibujar en el mapa" / "Subir archivo" · *KML, KMZ, GeoJSON o ZIP*
- Nota: "Tu lote no se guarda en ningún servidor externo."

**Paso Lluvia**
- Título: "¿Cuánto llueve?"
- Segmentado: Suave 30 mm · **Fuerte 80 mm** · Temporal 130 mm
- "Más opciones" plegable: Día real (selector de fecha + fuente real del dato) · Estado del suelo (Seco · Normal · Húmedo) · Manejo (Siembra directa con rastrojo · Suelo desnudo · Pastura)
- CTA: "Simular lluvia"
- Nota: "Lluvia de diseño regional, error ±20 %."

**Paso Resultado**
- Título: "Qué pasó con 80 mm"
- 3 métricas: **12 ha** *se encharcan* · **38 %** *escurre fuera del lote* · **4,2 t/ha** *suelo perdido*
- Lista: Dónde se encharca → · Por dónde escurre → · Pérdida de suelo → · Más análisis →
- "Detalles técnicos" plegable: CN, AMC, Manning, volúmenes, fuente y datum del relieve
- "Fuentes y límites" plegable: los 5 textos de limitación de la spec 001
- Acciones secundarias: "Cambiar lluvia" · "Exportar informe"

*Las cifras de ejemplo son ilustrativas para el diseño; en la app salen del modelo.*

---

## 9. Textos y tono

| Regla | Ejemplo correcto | Evitar |
|---|---|---|
| Frases cortas, voseo rioplatense | "Elegí tu lote" | "Ubicá o Dibujá tu Campo" (mayúsculas en cada palabra) |
| Primero la palabra de campo | "Dónde se encharca" · *profundidad máx.* | "Water depth max" |
| Sin mayúsculas sostenidas | "Antes de sembrar" | "ANTES DE SEMBRAR" |
| Sin signos ni emojis decorativos | "Simular lluvia" | "🚀 Calcular las 8 Herramientas" |
| Cifras con unidad y redondeo útil | "12 ha", "4,2 t/ha" | "12,3478 ha" |
| Fuente real y verificable | "Lluvia: NASA POWER · ~55 km" | "Red oficial SMN & CONAE" |
| Estados vacíos que guían | "Elegí un lote para empezar." | Indicadores sin datos |
| Errores con salida | "No pudimos descargar el relieve. Probá con un lote de ejemplo." | "422 Unprocessable Content" |

---

## 10. Accesibilidad

- Contraste AA: `#111` y `#666` sobre `#FFF` cumplen (≈ 18,9:1 y 5,7:1); el blanco sobre `#1E6B47` también (≈ 6,6:1).
- Foco visible: anillo de 2 px `--accent` con separación de 2 px.
- Objetivos táctiles de 44 × 44 px como mínimo.
- HTML semántico: `header`, `nav`, `main`, `section`, `footer`, `button`, `details`.
- El visor 3D tiene un texto alternativo con el resumen del resultado (`aria-live="polite"` al terminar la simulación).
- La información nunca depende solo del color: las leyendas llevan valores y unidad.
- `prefers-reduced-motion` y `prefers-color-scheme` respetados.

## 11. Rendimiento

| Métrica | Objetivo |
|---|---|
| Landing: tamaño total | < 150 kB sin la imagen; imagen hero en AVIF/WebP < 200 kB |
| App: JavaScript inicial | < 250 kB comprimido; Three.js y MapLibre con carga diferida |
| LCP (4G, celular medio) | < 2,5 s en la landing |
| CLS | < 0,05 |
| Fuente | Inter con `display=swap`, solo 3 pesos |

---

## 12. Cambios en el código

| Archivo | Acción |
|---|---|
| `apps/web/src/styles.css` | **Reescribir** sobre `tokens.css` (≈ 2.171 → < 600 líneas) |
| `apps/web/src/styles/tokens.css` | **Nuevo**: variables de color, tipografía, espacio y movimiento |
| `apps/web/src/App.tsx` | **Dividir**: `AppShell`, `StepNav`, `LotStep`, `RainStep`, `ResultStep` (< 400 líneas en total) |
| `components/ui/` | **Nuevo**: `Button`, `Segmented`, `OptionList`, `Metric`, `Details`, `BottomSheet`, `Legend`, `SourceNote`, `Icon` |
| `components/AgroLoadingOverlay.tsx` | **Reemplazar** por `ProgressBar` |
| `components/AgronomicToolkitPanel.tsx` | **Reorganizar** como "Más análisis" en una lista |
| `components/RainfallRunoffPanel.tsx` | **Simplificar** en `RainStep` + detalles plegables |
| `components/TerrainDiorama3D.tsx`, `TerrainScene3D.tsx` | **Solo estética**: fondo, paleta de datos, controles; sin tocar la física |
| `components/PolygonMapDrawer.tsx` | Estilos de controles y textos |
| `apps/web/public/landing.html` o ruta `/` | **Nuevo**: landing en un solo HTML según el prompt |

**Sin cambios:** `geoprocessing/`, `services/api/`, contratos de la API.

---

## 13. Criterios de aceptación

### Sistema visual
- [ ] Fuera del visor solo se usan los tokens de 6.1 (verificable con `grep` de colores en `styles/`).
- [ ] 0 `linear-gradient`/`radial-gradient` y 0 `box-shadow` fuera del visor (salvo la línea de la hoja inferior).
- [ ] 0 emojis en `apps/web/src` y en la landing.
- [ ] Una sola acción primaria (verde) visible por vista.
- [ ] Todos los números con cifras tabulares y unidad.

### Experiencia
- [ ] Con un lote de ejemplo: de abrir a ver el resultado en ≤ 3 decisiones y < 60 s (prueba con 3 personas sin experiencia técnica, tiempos anotados).
- [ ] Primera pantalla del simulador con ≤ 6 botones visibles.
- [ ] Visor ≥ 65% del ancho en escritorio y ≥ 55% del alto en el celular.

### Responsivo y accesibilidad
- [ ] Sin desplazamiento horizontal a 360, 390, 768, 1024 y 1440 px (capturas adjuntas).
- [ ] Lighthouse accesibilidad ≥ 95 en la landing y en `/app`.
- [ ] Navegación completa con teclado; foco visible.

### Landing (prompt)
- [ ] Un único archivo HTML con CSS integrado, variables, Flexbox y Grid.
- [ ] Separación entre secciones de 96–120 px; párrafos ≤ 65ch; `line-height: 1.1` en títulos.
- [ ] Navegación con máximo 4 enlaces.
- [ ] Transiciones de 0,2 s solo en botones y enlaces.
- [ ] Textos reales del proyecto, sin Lorem Ipsum.

### Técnico
- [ ] `npm run build` y `python -m pytest -q` en verde.
- [ ] JavaScript inicial < 250 kB comprimido.
- [ ] Ninguna atribución de datos que no sea la fuente real (coherente con la tarea 1 del pedido del 20/11).

---

## 14. Plan de trabajo

| Fase | Entregable | Agente | Rama |
|---|---|---|---|
| 0 | Aprobación de esta SDD y de la paleta (verde vs. otro acento) | Hernán | — |
| 1 | `tokens.css` + componentes `ui/` + página de muestra de componentes | frontend-3d | `feat/ui-sistema-minimalista` |
| 2 | Landing en un solo HTML según el prompt | frontend-3d | `feat/landing-minimalista` |
| 3 | Nuevo `AppShell` con flujo Lote → Lluvia → Resultado (escritorio) | frontend-3d | `feat/app-flujo-3-pasos` |
| 4 | Celular: hoja inferior, capas y gestos | frontend-3d | `feat/app-celular` |
| 5 | Visor: paleta de datos, controles y leyendas | frontend-3d | `feat/visor-estetica` |
| 6 | Limpieza: borrar CSS y componentes viejos; medir tamaños | frontend-3d + coordinador | `chore/ui-limpieza` |
| 7 | Prueba con 3 usuarios + Lighthouse + capturas | coordinador | — |

Cada fase en su PR; sin merge sin aprobación de Hernán.

---

## 15. Riesgos y decisiones pendientes

| # | Tema | Riesgo | Recomendación |
|---|---|---|---|
| R1 | **Choque con la tarea 2 del pedido del 20/11** (celular) | Trabajo duplicado: arreglar el diseño viejo y después tirarlo | Cancelar la tarea 2; el celular se resuelve en la fase 4 |
| R2 | Esconder herramientas | Que usuarios avanzados no encuentren TWI/SPI o Manning | "Más capas" y "Detalles técnicos" siempre a 1 toque |
| R3 | Rendimiento del 3D en celulares de gama baja | El visor protagonista exige más GPU | Calidad adaptativa y opción "Vista 2D" |
| R4 | Acento verde vs. vegetación del visor (NDVI) | Confusión de color | El NDVI usa una escala propia más amarillenta; el CTA nunca aparece dentro del visor |
| D1 | Acento | — | Verde campo `#1E6B47` (alternativa: negro sólido `#111111`, aún más estilo Apple) |
| D2 | Modo oscuro | Más trabajo de QA | Dejarlo para después de la fase 7 |
| D3 | Íconos | Librería o SVG propios | `lucide-react` con importación individual (liviano y consistente) |

---

## Anexo · Pedido listo para Antigravity

> Leé `AGENTS.md`, `docs/specs/001-modulo-escurrimiento.md` y `docs/specs/002-rediseno-minimalista.md`. Trabajá como **coordinador** con el agente **frontend-3d**. Ejecutá la SDD 002 por fases (1 a 6), una rama y un PR por fase, sin merge sin mi aprobación. **Cancelá la tarea 2 del pedido del 20/11** (celular), porque queda cubierta por la fase 4. No toques `geoprocessing/` ni `services/api/`. En cada PR adjuntá capturas a 390 y 1440 px y el tamaño del JavaScript inicial. Al terminar cada fase, tildá los criterios de la sección 13 que correspondan, con la evidencia.
