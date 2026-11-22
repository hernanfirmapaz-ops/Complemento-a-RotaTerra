"""Tests de verificación para el Issue #14 (Auditoría 7, 17 y 18 + revisión PR #35).

Criterios:
1. Calculadora de siembra y comparador de rotaciones fuera de la interfaz,
   anotados en docs/ como funciones de Rotaterra.
2. Borrar apps/web/src/components/AgroLoadingOverlay.tsx (no se usa).
3. Ningún texto que diga "INTA" sin dato del INTA.
4. PolygonMapDrawer.tsx no genera lotes de prueba preestablecidos.
"""

from __future__ import annotations

from tests.e2e.fixtures import REPO_ROOT


def test_agro_loading_overlay_is_deleted():
    """Auditoría 17: AgroLoadingOverlay.tsx era código muerto y debe estar eliminado."""
    overlay_path = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "components"
        / "AgroLoadingOverlay.tsx"
    )
    assert not overlay_path.exists(), (
        f"El archivo {overlay_path} todavía existe y debe ser eliminado."
    )


def test_polygon_map_drawer_has_no_preset_test_field_generator():
    """Revisión PR #35: PolygonMapDrawer no debe generar lotes de prueba preestablecidos."""
    drawer_path = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "components"
        / "PolygonMapDrawer.tsx"
    )
    assert drawer_path.exists()
    content = drawer_path.read_text(encoding="utf-8")

    assert "handleStampPolygonAtCenter" not in content, (
        "Se encontró handleStampPolygonAtCenter generando lotes preestablecidos en PolygonMapDrawer.tsx"
    )
    assert "Marcar lote aquí y ajustar" not in content, (
        "Se encontró el botón de generar lote preestablecido en PolygonMapDrawer.tsx"
    )


def test_no_unverified_inta_text_in_ui():
    """Auditoría 18: Ningún texto en UI debe citar al INTA sin respaldo de datos."""
    app_tsx = (REPO_ROOT / "apps" / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "Generando diagnóstico agronómico INTA / NASA" not in app_tsx, (
        "App.tsx contiene texto genérico 'Generando diagnóstico agronómico INTA / NASA'"
    )

    toolkit_panel = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "components"
        / "AgronomicToolkitPanel.tsx"
    ).read_text(encoding="utf-8")
    assert "Cultivo a sembrar (INTA)" not in toolkit_panel, (
        "AgronomicToolkitPanel.tsx contiene etiqueta 'Cultivo a sembrar (INTA)'"
    )
    assert "Siembra INTA" not in toolkit_panel, (
        "AgronomicToolkitPanel.tsx contiene pestaña 'Siembra INTA'"
    )

    result_step = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "components"
        / "flow"
        / "ResultStep.tsx"
    ).read_text(encoding="utf-8")
    assert "Suelo inferido según cartografía regional INTA" not in result_step, (
        "ResultStep.tsx contiene fallback inventado con mención al INTA"
    )
    assert "Carta INTA regional" not in result_step, (
        "ResultStep.tsx contiene fallback de suelo 'Carta INTA regional'"
    )


def test_seeding_calculator_and_rotation_comparator_removed_from_ui():
    """Auditoría 7: Calculadora de siembra y comparador de rotaciones fuera de la interfaz."""
    toolkit_panel = (
        REPO_ROOT
        / "apps"
        / "web"
        / "src"
        / "components"
        / "AgronomicToolkitPanel.tsx"
    ).read_text(encoding="utf-8")

    # Las pestañas de siembra y rotaciones no deben figurar en la botonera de la interfaz
    assert "'siembra'" not in toolkit_panel, (
        "La pestaña 'siembra' sigue activa en AgronomicToolkitPanel.tsx"
    )
    assert "'rotaciones'" not in toolkit_panel, (
        "La pestaña 'rotaciones' sigue activa en AgronomicToolkitPanel.tsx"
    )
    assert "8 Herramientas" not in toolkit_panel, (
        "El título de AgronomicToolkitPanel.tsx sigue diciendo 8 Herramientas"
    )


def test_docs_annotate_seeding_and_rotations_as_rotaterra_scope():
    """Auditoría 7: Documentación debe registrar siembra y rotaciones como funciones de Rotaterra."""
    arch_doc = (REPO_ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    limitations_doc = (REPO_ROOT / "docs" / "model-limitations.md").read_text(encoding="utf-8")

    full_docs = arch_doc + "\n" + limitations_doc
    assert "Rotaterra" in full_docs
    assert "siembra" in full_docs.lower()
    assert "rotaciones" in full_docs.lower()
    assert (
        "funciones de rotaterra" in full_docs.lower()
        or "alcance de rotaterra" in full_docs.lower()
        or "responsabilidad de rotaterra" in full_docs.lower()
    ), "No se encontró mención explícita delimitando siembra y rotaciones como alcance de Rotaterra en docs/"
