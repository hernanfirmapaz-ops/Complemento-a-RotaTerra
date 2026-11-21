"""Salida del módulo para Rotaterra en el contrato `Observacion` de N4-4-1.2 (spec 011).

Solo lee resultados ya calculados: no dispara cálculos ni consultas a internet.
Nunca inventa un valor: lo que falta sale con `valor=None`, `calidad="descartada"` y el motivo.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from services.api.app.services import store

FUENTE_MODELO = "Complemento RotaTerra"  # resultados calculados por este módulo
MAX_FUENTE = 32
GRUPOS = {"A": 1, "B": 2, "C": 3, "D": 4}


def _fecha(texto: str | None) -> str:
    if texto:
        try:
            return datetime.fromisoformat(texto.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return date.today().isoformat()


def _fuente(nombre: str | None) -> str:
    nombre = (nombre or FUENTE_MODELO).strip() or FUENTE_MODELO
    return nombre[:MAX_FUENTE]


def _obs(lote_id, fecha, variable, valor, unidad, fuente, resolucion_m, calidad, nota="") -> dict:
    if valor is None:
        calidad = "descartada"
    return {
        "lote_id": lote_id,
        "fecha": fecha,
        "variable": variable,
        "valor": None if valor is None else round(float(valor), 4),
        "unidad": unidad,
        "fuente": _fuente(fuente),
        "resolucion_m": int(round(resolucion_m or 0)),
        "calidad": calidad,
        "nota": nota,
    }


def _cargar(fn, *args):
    try:
        return fn(*args)
    except store.NotFound:
        return None


def _leer_json(ruta) -> dict | None:
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def _elegir_corrida(runs: list[dict], run_id: str | None) -> dict | None:
    if run_id:
        for r in runs:
            if r.get("id") == run_id:
                return r
        raise store.NotFound(f"runoff_run:{run_id}")
    activas = [r for r in runs if r.get("is_active")]
    candidatas = activas or runs
    return max(candidatas, key=lambda r: r.get("created_at", "")) if candidatas else None


def observaciones_del_lote(field_id: str, run_id: str | None = None) -> list[dict]:
    field = store.load_field(field_id)
    lote = field_id
    terreno = _cargar(store.load_terrain, field_id)
    hidro = _cargar(store.load_hydrology, field_id)
    runs = store.list_runoff_runs(field_id)
    corrida = _elegir_corrida(runs, run_id)
    carpeta = store.field_dir(field_id)
    suelo = _leer_json(carpeta / "soil.json")
    toolkit = _leer_json(carpeta / "toolkit.json")

    out: list[dict] = []

    # --- Relieve ---
    fuente_mde = (terreno or {}).get("source", {}).get("source_name")
    res_mde = (terreno or {}).get("quality", {}).get("pixel_size_m") or (terreno or {}).get("source", {}).get(
        "nominal_resolution_m"
    )
    cal_mde = "buena" if res_mde and float(res_mde) <= 5 else "dudosa"
    f_terr = _fecha((terreno or {}).get("processed_at"))
    sin_relieve = "Sin relieve procesado para el lote."
    area = (terreno or {}).get("quality", {}).get("field_area_ha") or field.get("area_ha")
    out.append(_obs(lote, f_terr, "superficie_lote_ha", area, "ha", "Polígono del lote", 0, "buena",
                    "" if area is not None else "Sin superficie calculada."))

    resumen = (hidro or {}).get("summary", {})
    f_hid = _fecha((hidro or {}).get("processed_at"))
    sin_hidro = "Sin hidrología estática calculada para el lote."
    nota_mde = f"Datum {terreno['quality'].get('vertical_datum')}" if terreno else sin_relieve
    out.append(_obs(lote, f_hid, "pendiente_media_pct", resumen.get("mean_slope_in_field_pct"), "%",
                    fuente_mde, res_mde, cal_mde,
                    nota_mde if resumen.get("mean_slope_in_field_pct") is not None else sin_hidro))
    for variable, clave, unidad in (
        ("bajos_area_ha", "total_depression_area_in_field_ha", "ha"),
        ("bajos_volumen_m3", "total_depression_volume_in_field_m3", "m³"),
        ("aporte_externo_ha", "external_inflow_ha", "ha"),
    ):
        valor = resumen.get(clave) if hidro else None
        out.append(_obs(lote, f_hid, variable, valor, unidad, fuente_mde, res_mde, cal_mde,
                        "" if valor is not None else sin_hidro))

    # --- Suelo (spec 004) ---
    tiene_suelo = bool(suelo and suelo.get("soil_group"))
    cal_suelo = suelo.get("quality", "descartada") if tiene_suelo else "descartada"
    fuente_suelo = suelo.get("source_label", "").split(" · ")[0] if tiene_suelo else "Sin fuente de suelos"
    res_suelo = suelo.get("resolution_m") if tiene_suelo else 0
    nota_suelo = "" if tiene_suelo else "No se consultó o no hay datos de suelo para el lote."
    for variable, clave in (("arcilla_pct", "clay_pct"), ("arena_pct", "sand_pct"), ("limo_pct", "silt_pct")):
        out.append(_obs(lote, _fecha(None), variable, suelo.get(clave) if tiene_suelo else None, "%",
                        fuente_suelo, res_suelo, cal_suelo, nota_suelo))
    grupo = suelo.get("soil_group") if tiene_suelo else None
    out.append(_obs(lote, _fecha(None), "grupo_hidrologico", GRUPOS.get(grupo) if grupo else None, "código 1-4",
                    fuente_suelo, res_suelo, cal_suelo,
                    f"Grupo {grupo} ({suelo.get('texture_class')}); 1=A, 2=B, 3=C, 4=D" if grupo else nota_suelo))

    # --- Corrida de lluvia y escurrimiento ---
    sin_corrida = "Sin corrida de lluvia y escurrimiento para el lote."
    if corrida:
        f_run = _fecha(corrida.get("created_at"))
        cn = corrida.get("cn_result", {})
        esp = corrida.get("spatial_summary", {})
        nivel = (corrida.get("confidence") or {}).get("level")
        cal_run = "buena" if nivel == "alto" else "dudosa"
        eventos = {e.get("id"): e for e in store.list_rainfall_events(field_id)}
        tipo_lluvia = str(eventos.get(corrida.get("rainfall_event_id"), {}).get("source_type") or "")
        nota_run = f"Corrida '{corrida.get('name', '')}' · confianza {nivel or 'sin dato'}"
        cal_lluvia = "buena" if tipo_lluvia.lower() in ("gauge", "pluviometro", "local_pluviometer") else "dudosa"
        out.append(_obs(lote, f_run, "lluvia_evento_mm", cn.get("precipitation_mm"), "mm",
                        corrida.get("rainfall_event_name") or FUENTE_MODELO, 0, cal_lluvia, nota_run))
        coef = cn.get("runoff_coefficient")
        for variable, valor, unidad in (
            ("escurrimiento_mm", cn.get("runoff_q_mm"), "mm"),
            ("coeficiente_escurrimiento_pct", None if coef is None else coef * 100.0, "%"),
            ("volumen_escurrido_m3", esp.get("field_runoff_generated_m3"), "m³"),
            ("caudal_pico_m3_s", esp.get("peak_discharge_m3_s"), "m³/s"),
        ):
            out.append(_obs(lote, f_run, variable, valor, unidad, FUENTE_MODELO, res_mde, cal_run, nota_run))
        h2d = corrida.get("hydrodynamic_2d_summary") or {}
        encharcada = h2d.get("ponded_area_in_field_ha")
        out.append(_obs(lote, f_run, "area_encharcada_ha", encharcada, "ha", FUENTE_MODELO, res_mde, cal_run,
                        nota_run if encharcada is not None else
                        "La corrida no tiene simulación 2D: el área encharcada no se estima."))
    else:
        for variable, unidad in (("lluvia_evento_mm", "mm"), ("escurrimiento_mm", "mm"),
                                 ("coeficiente_escurrimiento_pct", "%"), ("volumen_escurrido_m3", "m³"),
                                 ("caudal_pico_m3_s", "m³/s"), ("area_encharcada_ha", "ha")):
            out.append(_obs(lote, _fecha(None), variable, None, unidad, FUENTE_MODELO, 0, "descartada", sin_corrida))

    # --- Erosión (USLE por tormenta) ---
    usle = (toolkit or {}).get("erosion_usle") or {}
    perdida = usle.get("mean_soil_loss_t_ha")
    out.append(_obs(lote, _fecha((toolkit or {}).get("processed_at")), "perdida_suelo_t_ha", perdida, "t/ha",
                    "USLE (Wischmeier y Smith)", res_mde, "dudosa",
                    "Pérdida media por la tormenta analizada" if perdida is not None
                    else "Sin herramientas agronómicas calculadas para el lote."))
    return out
