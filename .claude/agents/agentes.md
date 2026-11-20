# Equipo de agentes

Complemento a RotaTerra se desarrolla con un equipo de cinco agentes de Claude Code, definido en `.claude/agents/`. La división sigue las capas de la arquitectura (ver `architecture.md`), de modo que cada agente es dueño de un área del repositorio y los límites entre ellos coinciden con los contratos del sistema.

## Composición

| Agente | Archivo | Responsabilidad | Área del repositorio | Modelo |
|---|---|---|---|---|
| Coordinador | `.claude/agents/coordinador.md` | Planificación, delegación, revisión e integración | Todo (lectura) | Opus |
| Hidrólogo | `.claude/agents/hidrologo.md` | Modelos hidrológicos, de suelo y agronómicos | `geoprocessing/` | Opus |
| Experto en datos NASA | `.claude/agents/experto-datos-nasa.md` | Selección, descarga, calidad y trazabilidad de datos satelitales y climáticos | `geoprocessing/satellite/`, `net.py`, `dem/sources.py`, `docs/data-sources.md` | Opus |
| Backend | `.claude/agents/backend.md` | API, contratos, orquestación y caché | `services/api/` | Sonnet |
| Frontend 3D | `.claude/agents/frontend-3d.md` | Visor web, capas y experiencia de uso | `apps/web/` | Sonnet |

## Por qué cinco

- Tres agentes separan las capas técnicas (modelo, API, visor) y uno concentra el control de calidad.
- Los datos NASA tienen su propia complejidad (productos, versiones, resoluciones, máscaras de calidad, credenciales Earthdata), por lo que se separan de `backend` en un especialista dedicado.
- Más agentes aumentarían el costo de coordinación sin beneficio en un proyecto personal de mantenimiento individual. El siguiente candidato natural, si el proyecto crece, es uno de **QA/documentación**.

## Flujo

```
Responsable
   │  pedido
   ▼
Coordinador ── plan + criterios de aceptación
   │
   ├─► Experto datos NASA (datos + calidad + metadatos)
   │       │ arreglos, unidades, limitaciones
   ├─► Hidrólogo   (modelo + tests)
   │       │ firma y unidades
   ├─► Backend     (endpoint + schema + tests)
   │       │ contrato
   └─► Frontend 3D (visualización + build)
           │
           ▼
Coordinador ── revisión + verificación completa ── PR a main ── reporte al responsable
```

## Contratos entre agentes

| De → A | Qué se entrega |
|---|---|
| Experto datos NASA → Hidrólogo | Datos recortados al lote, unidades, metadatos y limitaciones de escala |
| Hidrólogo → Backend | Firma de la función pública, unidades de entrada y salida, supuestos |
| Backend → Frontend 3D | Schema Pydantic final y ejemplo de respuesta |
| Todos → Coordinador | Diff, resultado de tests/build y lista de riesgos |

## Definición de terminado (común)

1. `python -m pytest -q` en verde.
2. `npm run build` en `apps/web/` en verde.
3. Fórmulas con fuente citada y test de referencia.
4. Contratos sincronizados entre `schemas.py` y `types/api.ts`.
5. Documentación de `docs/` actualizada cuando corresponda.
6. Ningún test depende de internet.

## Uso

En Claude Code, iniciar cualquier pedido que involucre más de una capa con el agente `coordinador`. Para tareas acotadas a una sola capa se puede invocar directamente al especialista correspondiente.
