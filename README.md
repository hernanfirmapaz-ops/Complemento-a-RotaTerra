# Complemento a RotaTerra

Módulos complementarios de [RotaTerra](#) (NASA Space Apps Challenge 2026 · San Luis).

## Módulos

| Módulo | Carpeta | Estado |
|---|---|---|
| Escurrimiento: simulación 3D de lluvia, infiltración y escurrimiento sobre el terreno del lote | [`escurrimiento/`](escurrimiento/) | Prototipo |

## Escurrimiento

Página única (HTML + Three.js r128 por CDN), sin build. Abrir `escurrimiento/index.html` en el navegador.

- **Terreno:** 4 terrenos sintéticos de ejemplo, o carga de un `.asc` (MDE recortado en QGIS: SRTM, Copernicus GLO-30, MDE-Ar IGN) o una imagen de alturas en gris.
- **Agua:** modelo de agua somera con tuberías virtuales (grilla 128 × 128, 1 paso = 1 s).
- **Infiltración:** según suelo (arenoso, franco, arcilloso, compactado), cobertura (desnudo, rastrojo, pastura) y humedad acumulada.
- **Salidas:** % infiltrado, % que salió del lote, % del área anegada, hidrograma y líneas de escurrimiento (D8).

> Modelo simplificado: sirve para comparar escenarios, no para diseño hidráulico.

## Próximos pasos

- [ ] Traer el MDE del lote elegido en RotaTerra automáticamente
- [ ] Erosión / arrastre de suelo
- [ ] Lluvia real (NASA GPM) por fecha
