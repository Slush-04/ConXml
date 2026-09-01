"""Prueba de integración contra el servicio real del SAT.

Se ejecuta solo con: python -m pytest -m integration
Lee el primer comprobante del catálogo local y consulta su estatus real.
"""

from pathlib import Path

import pytest

from conxml.catalog.db import Catalogo
from conxml.sat.soap import consultar


@pytest.mark.integration
def test_consulta_real_contra_sat():
    ruta_db = Path("data/catalogo.db")
    if not ruta_db.exists():
        pytest.skip("no existe data/catalogo.db con el catálogo real")

    with Catalogo(ruta_db) as catalogo:
        fila = next(catalogo.consulta())
        resultado = consultar(
            uuid=fila["uuid"],
            rfc_emisor=fila["emisor_rfc"],
            rfc_receptor=fila["receptor_rfc"],
            total=fila["total"],
        )
        print(f"\nUUID: {fila['uuid']} -> {resultado}")
        assert resultado.estado in {"Vigente", "Cancelado", "No Encontrado"}