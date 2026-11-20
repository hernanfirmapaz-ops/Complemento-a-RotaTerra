# Complemento a RotaTerra · Instrucciones para agentes (Antigravity)

Copiar este archivo a la raíz del repositorio `Complemento-a-RotaTerra`. Si Antigravity no lo toma automáticamente, cargar su contenido como regla del workspace.

## Proyecto

Web app que simula el terreno real de un lote agrícola de la llanura de San Luis (20–500 ha) y cómo drena el suelo y corre el agua. Complementa a Rotaterra (rotación de cultivos con datos NASA; pipeline en `hernanfirmapaz-ops/N4-4-1.2`). Proyecto personal de Hernán Firmapaz, mantenido por una sola persona: priorizar simplicidad y mantenibilidad.

- `geoprocessing/` — núcleo científico en Python (MDE, flujo, CN, agua somera 2D, USLE, balance hídrico)
- `services/api/` — FastAPI
- `apps/web/` — React 19 + TypeScript + Three.js + MapLibre (Vite)

## Documentos de referencia (leer antes de empezar)

| Archivo | Contenido |
|---|---|
| `docs/investigacion-escurrimiento.md` | Fuentes de relieve, suelos, CN, lluvias de diseño, erosión, napa, motor hidrológico |
| `docs/brechas-codigo-vs-investigacion.md` | Qué falta o está mal en el código actual (anomalías A1–A4) |
| `docs/specs/001-modulo-escurrimiento.md` | Spec vigente: entradas, proceso, salidas, criterios de aceptación y fases |
| `docs/agentes/*.md` | Perfiles completos de los 5 roles |

## Reglas

1. **Spec primero (SDD).** Nada de código sin spec aprobada por Hernán. Un criterio se tilda solo cuando se verificó, anotando los números.
2. **Nunca inventar un valor.** Si falta un dato: `valor: null` + `calidad: "descartada"` + motivo. Prohibido generar datos sintéticos en el camino productivo (ver anomalía A1).
3. **Contrato común.** Todo valor escalar sale como `Observacion` de N4-4-1.2 (`lote_id, fecha, variable, valor, unidad, fuente, resolucion_m, calidad, nota`); los rasters agregan `raster_ref` (URI de COG).
4. **Fuentes.** NASA + INTA + productor, más las excepciones aprobadas en la spec (IGN, Copernicus DEM, INA/CONICET). FABDEM solo en modo no comercial.
5. **Datum vertical siempre declarado.** SRVN16 (IGN) ≠ EGM2008 (Copernicus) ≠ EGM96 (NASADEM/SRTM).
6. **Separación de capas.** La física vive en `geoprocessing/`; la API no recalcula; el navegador no simula.
7. **Pruebas.** `python -m pytest -q` y `npm run build` (en `apps/web/`) en verde. Ningún test accede a internet (`httpx.MockTransport`, fixtures).
8. **Secretos.** `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`, `OPENTOPOGRAPHY_API_KEY` solo como variables de entorno o secretos de GitHub; nunca en código, commits ni logs.
9. **Git.** Una rama por tarea (`feat/…`, `fix/…`, `docs/…`); Conventional Commits; PR hacia `main`; Hernán aprueba el merge. No subir nada sin su pedido explícito.
10. **Idioma.** Textos de interfaz y documentación en español rioplatense; unidades agronómicas (mm, t/ha, ha, %).

## Roles

| Rol | Área | Hace | No hace |
|---|---|---|---|
| Coordinador | Todo (lectura) | Plan, criterios, delegación, revisión, integración | Código de producción |
| Experto en datos NASA | `geoprocessing/satellite/`, `net.py`, `dem/sources.py`, `docs/data-sources.md` | Elegir producto y versión, descargar, recortar, control de calidad, metadatos | Modelos físicos |
| Hidrólogo | `geoprocessing/hydrology`, `rainfall`, `agronomy`, `dem` | Fórmulas con fuente, unidades SI, tests de referencia y conservación | Red, endpoints |
| Backend | `services/api/` | Endpoints, schemas, caché, errores, orquestación | Física, descarga satelital |
| Frontend 3D | `apps/web/` | Visor, capas, paneles, celular, textos de limitación | Simular en el navegador |

Orden de trabajo de cada tarea: datos → modelo → API → visor → revisión del coordinador.

## Primer paso sugerido

Fase 0 de la spec: verificar la cobertura del MDT 5 m del IGN en General Pedernera, pedir la API key de OpenTopography y eliminar el respaldo climático sintético (A1).
