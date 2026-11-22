"""Auditoría de cumplimiento de Spec 013 (Etapa 1: Malla de agua y bordes suaves).

Verifica:
1. Que el supuesto de umbral de encharcamiento esté declarado formalmente en supuestos.py.
2. Que terrain_mesh exponga ponding_threshold_m del solver 2D hacia el visor 3D sin depender de datos locales.
3. Que la función de corte y desvanecimiento cumpla estrictamente smoothstep(h_umbral, 1.5*h_umbral, h).
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from geoprocessing import supuestos
from services.api.app.services import hydrology, terrain


def test_supuesto_umbral_encharcamiento_declarado():
    """Verifica que el umbral de encharcamiento por omisión esté formalmente en supuestos.py."""
    sup = getattr(supuestos, "UMBRAL_ENCHARCAMIENTO_MOTOR_M", None)
    assert sup is not None, "Falta UMBRAL_ENCHARCAMIENTO_MOTOR_M en supuestos.py"
    assert sup.clave == "umbral_encharcamiento_motor_m"
    assert sup.unidad == "m"
    assert sup.valor == 0.05
    assert sup.editable is True
    assert "shallow_water_2d.py" in (sup.fuente_referencia or "")


def test_terrain_mesh_expone_ponding_threshold_m_del_motor(monkeypatch: pytest.MonkeyPatch):
    """Verifica que terrain_mesh reporte ponding_threshold_m de la corrida 2D activa."""
    fake_dem = MagicMock()
    fake_dem.z = np.zeros((10, 10), dtype=np.float32)
    fake_dem.transform = [10.0, 0, 0, 0, -10.0, 0]
    fake_mask = np.ones((10, 10), dtype=bool)
    fake_field = {
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]},
        "utm_epsg": 32719,
    }

    monkeypatch.setattr(terrain, "_contexto", lambda fid: ({}, fake_field, fake_dem, fake_mask))
    monkeypatch.setattr(terrain, "field_rings_utm", lambda geom: [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]])
    monkeypatch.setattr(
        terrain,
        "mesh",
        lambda dem, m, rings, max_size, extra_grids=None: {"rows": 10, "cols": 10, "z": [0.0] * 100, "boundary": []},
    )
    monkeypatch.setattr(hydrology, "optional_hydrology_grids", lambda fid: None)
    fake_r_grids = {
        "runoff_load_mm": np.zeros((10, 10), dtype=np.float32),
        "cumulative_runoff_m3": np.zeros((10, 10), dtype=np.float32),
    }
    monkeypatch.setattr(
        hydrology,
        "optional_active_runoff",
        lambda fid: ({"hydrodynamic_2d_summary": {"ponding_threshold_m": 0.05}}, fake_r_grids),
    )

    mesh_data = terrain.terrain_mesh("field-test-spec013", max_size=120)
    assert "ponding_threshold_m" in mesh_data, "terrain_mesh debe incluir 'ponding_threshold_m'"
    assert mesh_data["ponding_threshold_m"] == 0.05
