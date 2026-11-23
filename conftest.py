"""Configuración global de pytest para Complemento a RotaTerra.

Aísla completamente la persistencia en disco de los tests para evitar contaminar
la base local de desarrollo (`data/runs/`) con lotes sintéticos o corridas de prueba.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def isolate_test_data_dir(tmp_path_factory: pytest.TempPathFactory):
    test_runs = tmp_path_factory.mktemp("isolated_test_runs")
    os.environ["ROTATERRA_DATA_DIR"] = str(test_runs)
    try:
        from services.api.app.core import config
        from services.api.app.services import store
        config.DATA_DIR = test_runs
        store.DATA_DIR = test_runs
    except ImportError:
        pass
