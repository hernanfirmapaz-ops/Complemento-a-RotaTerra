# Metodología de trabajo · Complemento a RotaTerra

**Vigente desde:** 21/11/2026 · **Aplica a:** Hernán, Claude y Antigravity, sin excepciones.

---

## 1. Ciclo obligatorio de cada tarea

| Paso | Qué se hace | Quién | Sale de acá |
|---|---|---|---|
| 1. Spec | Problema, alcance, fuera de alcance, criterios de aceptación medibles, fuentes de datos | Claude / Antigravity | `docs/specs/NNN-*.md` aprobado por Hernán |
| 2. Test primero | Test que falla y demuestra lo que falta o el error | Quien implementa | Test en rojo |
| 3. Código | El mínimo cambio que hace pasar el test | Quien implementa | Test en verde |
| 4. Verificación local | `pytest`, `ruff`, `npm run build` y prueba visual en la app | Quien implementa | Captura o salida pegada en el PR |
| 5. Pull request | Rama propia, plantilla de PR completa | Quien implementa | PR abierto |
| 6. Revisión | Checklist de la sección 4 punto por punto | Claude (si implementó Antigravity) o Antigravity (si implementó Claude) | Aprobado / cambios pedidos |
| 7. Merge | Solo con revisión automática en verde y checklist completo | **Hernán** | `main` actualizado |

**Nadie se revisa a sí mismo. Nadie empuja directo a `main`.**

---

## 2. Regla de datos (la más importante)

Todo número que llega a la pantalla o a Rotaterra tiene **exactamente uno** de estos tres estados:

| Estado | Requisito | Cómo se muestra |
|---|---|---|
| **Dato con fuente** | Fuente **consultada**: documento + página/tabla o URL + fecha de consulta, anotada en `docs/data-sources.md` | Valor + fuente |
| **Supuesto editable** | Declarado en un único archivo de supuestos, con motivo; el usuario lo puede cambiar | Valor + etiqueta "supuesto" |
| **Sin dato** | — | `null` + calidad "descartada" + motivo |

Prohibido:
- Valores de respaldo silenciosos (`or 1.5`, `max(120, …)`, `0.0` cuando falta el dato).
- Citar un autor u organismo sin haber leído la fórmula en el documento.
- Marcar reanálisis o modelos como "observado".

Si una cita no se pudo verificar, **no se cita**: se pasa a supuesto o se elimina.

---

## 3. Formato de pedido para Antigravity

Cada pedido usa estos encabezados, sin excepción:

1. **Objetivo**, en una frase.
2. **Contexto**: qué existe hoy, con archivos y líneas.
3. **Alcance**, en una lista cerrada.
4. **Fuera de alcance**: lo que NO debe tocar.
5. **Criterios de aceptación**: cada uno verificable con un test o un comando.
6. **Fuentes de datos** permitidas, con referencia exacta.
7. **Rama y commits**: nombre de rama; Conventional Commits.
8. **Verificación**: comandos a correr y qué pegar en el PR.
9. **Cuándo frenar**: condición para detenerse y reportar en lugar de improvisar.

---

## 4. Checklist de revisión (plantilla de PR)

```markdown
## Qué cambia
<!-- una o dos frases -->

## Spec / tarea
<!-- docs/specs/NNN o tarea A# -->

## Verificación
- [ ] Test nuevo que fallaba antes del cambio
- [ ] `pytest` en verde (pegar resumen)
- [ ] `ruff check .` sin errores
- [ ] `npm run build` sin errores
- [ ] Captura de la app si cambia la interfaz

## Datos
- [ ] Ningún número nuevo sin fuente consultada, supuesto declarado o `null`
- [ ] Fuentes nuevas agregadas a `docs/data-sources.md`
- [ ] Sin valores de respaldo silenciosos

## Alcance
- [ ] Solo agua, relieve, suelo y erosión (nada de economía ni rotaciones)
- [ ] Sin cambios fuera del alcance del pedido

## Seguridad
- [ ] Sin secretos, claves ni datos de corridas
- [ ] Tests sin internet
```

---

## 5. Reglas de Git

| Regla | Detalle |
|---|---|
| Una rama por tarea | `feat/`, `fix/`, `docs/`, `refactor/`, `chore/`, `perf/` + nombre corto |
| Commits chicos | Un cambio lógico por commit; Conventional Commits en español |
| PR chico | Máximo ~400 líneas cambiadas; si es más, se parte |
| Protección de `main` | Activar en GitHub: PR obligatorio + revisión automática en verde para mergear |
| Ramas mergeadas | Se borran después del merge |

---

## 6. Cuando aparece un error

1. **Test que lo reproduce**, antes de corregir.
2. Corrección mínima.
3. Una línea en `docs/registro-errores.md`: fecha · qué pasó · causa · cómo se evita que vuelva.
4. Si el error fue de método (por ejemplo, una cita sin verificar), se ajusta esta metodología.

---

## 7. Controles periódicos

| Cuándo | Qué |
|---|---|
| Cada PR | Checklist de la sección 4 |
| Cada 5 PR mergeados o cada semana | Auditoría corta: tests, `npm audit`, `pip-audit`, búsqueda de números sin fuente |
| Antes de publicar (Render u otro) | Auditoría completa como la del 21/11 + prueba manual del flujo completo |

---

## 8. Herramientas a sumar (tarea A5, rama `chore/calidad`)

- [x] `.github/pull_request_template.md` con el checklist de la sección 4
- [ ] Protección de rama en `main` (la activa Hernán en GitHub: Settings → Branches)
- [ ] `pre-commit` con Ruff (evita commits con errores de formato)
- [x] ESLint + Vitest en el frontend, sumados a la revisión automática
- [x] `docs/registro-errores.md`
- [x] Archivo único de supuestos (`geoprocessing/supuestos.py`) con valor, unidad y motivo de cada uno

---

## 9. Seguridad automática: Dependabot y CodeQL

Para alertar proactivamente sobre vulnerabilidades en librerías y dependencias (como ocurrió con MapLibre GL) y analizar estáticamente el código:

1. **Configuración manual en GitHub (Hernán):**
   - Settings → *Code security* → activar *Dependabot alerts* y *Dependabot security updates*.
   - Settings → *Code security* → *Code scanning* → *CodeQL analysis* → *Default*.

2. **Automatización en el repositorio (`.github/dependabot.yml`):**
   - **Ecosistemas cubiertos:**
     - `pip` (directorio `/` para backend y geoprocesamiento).
     - `npm` (directorio `/apps/web` para frontend).
     - `github-actions` (directorio `/` para flujos de CI).
   - **Frecuencia:** Semanal (`weekly`).
   - **Agrupamiento:** Actualizaciones menores y parches agrupados en un solo PR por ecosistema (`minor`, `patch`) para evitar dispersión de PRs.
   - **Límite de PRs:** Máximo 3 PRs abiertos simultáneamente por Dependabot.

3. **Flujo de revisión y merge de PRs de Dependabot:**
   - Cada PR de Dependabot corre la revisión automática de CI (`verificar.yml`).
   - Pasa por la misma revisión obligatoria (Claude) bajo el checklist de la sección 4.
   - **Solo Hernán** mergea los PRs una vez aprobados y con CI en verde.

