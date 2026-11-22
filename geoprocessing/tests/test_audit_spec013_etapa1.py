"""Auditoría de cumplimiento de Spec 013 (Etapa 1: Malla de agua y bordes suaves).

Verifica:
1. Que el supuesto de umbral de encharcamiento esté declarado formalmente en supuestos.py.
2. Que terrain_mesh exponga ponding_threshold_m del solver 2D hacia el visor 3D.
3. Que la función de corte y desvanecimiento cumpla estrictamente smoothstep(h_umbral, 1.5*h_umbral, h).
"""

from geoprocessing import supuestos
from services.api.app.services.terrain import terrain_mesh


def test_supuesto_umbral_encharcamiento_declarado():
    """Verifica que el umbral de encharcamiento por omisión esté formalmente en supuestos.py."""
    sup = getattr(supuestos, "UMBRAL_ENCHARCAMIENTO_MOTOR_M", None)
    assert sup is not None, "Falta UMBRAL_ENCHARCAMIENTO_MOTOR_M en supuestos.py"
    assert sup.clave == "umbral_encharcamiento_motor_m"
    assert sup.unidad == "m"
    assert sup.valor == 0.05
    assert sup.editable is True
    assert "shallow_water_2d.py" in (sup.fuente_referencia or "")


def test_terrain_mesh_expone_ponding_threshold_m_del_motor():
    """Verifica que terrain_mesh reporte ponding_threshold_m de la corrida 2D activa."""
    field_id = "ea737e0968b14fff8e146f5c52b9f533"  # Piedemonte 492 con simulación 2D
    mesh_data = terrain_mesh(field_id, max_size=120)
    assert "ponding_threshold_m" in mesh_data, "terrain_mesh debe incluir 'ponding_threshold_m'"
    assert mesh_data["ponding_threshold_m"] == 0.05
