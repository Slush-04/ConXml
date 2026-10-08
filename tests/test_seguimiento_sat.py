"""Recuperación automática de solicitudes SAT sin depender del servicio externo."""
import json
from types import SimpleNamespace

import pytest

from conxml import estado_local
from conxml.catalog.db import Catalogo
from conxml.config import Config
from conxml.sat.descarga_masiva import RespuestaSAT
from conxml.sat.seguimiento import procesar_solicitud
from conxml.ui.pantalla_descargas import PantallaDescargas


def _solicitud(db_path, id_sat="SOL1", rfc="EKU9003173C9", estado=1):
    with Catalogo(db_path) as catalogo:
        catalogo.guardar_solicitud_descarga(
            cliente="C1", rfc=rfc, direccion="Emitidos",
            fecha_inicial="2024-02-01", fecha_final="2024-02-29",
            tipo_comprobante="", id_sat=id_sat, cod_estatus="5000",
            estado=estado, mensaje="Aceptada",
        )
        return dict(catalogo.obtener_solicitud_descarga(id_sat))


def test_seguimiento_espera_paquetes_y_continua_tras_fallo(tmp_path, monkeypatch):
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    estado_local.guardar({"descargas_sat": {"modo": "zip"}})
    config = Config()
    datos = _solicitud(config.db_path)

    class SAT:
        def __init__(self):
            self.paquetes = []
            self.fallar_en_p2 = True
            self.con_ids = False

        def verificar(self, rfc, id_sat):
            assert (rfc, id_sat) == (datos["rfc"], "SOL1")
            return RespuestaSAT(
                estado=3, cod_estatus="5000", numero_cfdis=2,
                paquetes=["P1", "P2"] if self.con_ids else [],
            )

        def descargar_paquete(self, rfc, paquete):
            self.paquetes.append(paquete)
            if paquete == "P2" and self.fallar_en_p2:
                raise RuntimeError("fallo de conexión simulado")
            return paquete.encode()

    sat = SAT()
    pendiente = procesar_solicitud(sat, config.db_path, datos, config)
    assert not pendiente.recuperada
    assert sat.paquetes == []
    with Catalogo(config.db_path) as catalogo:
        assert len(catalogo.solicitudes_descarga_pendientes({datos["rfc"]})) == 1

    sat.con_ids = True
    with pytest.raises(RuntimeError, match="simulado"):
        procesar_solicitud(sat, config.db_path, datos, config)
    with Catalogo(config.db_path) as catalogo:
        fila = catalogo.obtener_solicitud_descarga("SOL1")
        assert fila["recuperado"] == 0
        assert json.loads(fila["paquetes_recuperados_json"]) == ["P1"]
    assert (config.carpeta_zip_sat / "C1" / "SOL1" / "P1.zip").read_bytes() == b"P1"

    sat.fallar_en_p2 = False
    with Catalogo(config.db_path) as catalogo:
        datos = dict(catalogo.obtener_solicitud_descarga("SOL1"))
    terminado = procesar_solicitud(sat, config.db_path, datos, config)
    assert terminado.recuperada
    assert sat.paquetes == ["P1", "P2", "P2"]
    with Catalogo(config.db_path) as catalogo:
        fila = catalogo.obtener_solicitud_descarga("SOL1")
        assert fila["recuperado"] == 1
        assert json.loads(fila["paquetes_recuperados_json"]) == ["P1", "P2"]
        assert catalogo.solicitudes_descarga_pendientes({datos["rfc"]}) == []


def test_revision_automatica_procesa_pendiente_y_vuelve_a_programarse(tmp_path, monkeypatch):
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    estado_local.guardar({"descargas_sat": {"modo": "zip"}})
    config = Config()
    datos = _solicitud(config.db_path)
    llamadas, programaciones, resultados = [], [], []

    class SAT:
        def __init__(self, fiel):
            assert fiel.rfc == datos["rfc"]

        def verificar(self, rfc, id_sat):
            llamadas.append((rfc, id_sat))
            return RespuestaSAT(estado=3, cod_estatus="5000", numero_cfdis=1, paquetes=["P1"])

        def descargar_paquete(self, rfc, paquete):
            return b"ZIP"

        def cerrar(self):
            pass

    monkeypatch.setattr("conxml.ui.pantalla_descargas.ClienteDescargaSAT", SAT)
    app = SimpleNamespace(
        db_path=config.db_path, _ocupada=False,
        ejecutar=lambda trabajo, presentar, *args, **kwargs: (presentar(trabajo()), True)[1],
    )
    pantalla = SimpleNamespace(
        app=app, _firmas_activas={datos["rfc"]: SimpleNamespace(rfc=datos["rfc"])},
        _revision_after="timer", _programar_revision=lambda: programaciones.append(True),
        _presentar_revision_automatica=lambda valor: resultados.extend(valor),
        _error_revision_automatica=lambda exc: pytest.fail(str(exc)),
    )
    PantallaDescargas._revision_automatica(pantalla)
    assert llamadas == [(datos["rfc"], "SOL1")]
    assert resultados[0][1].recuperada
    assert pantalla._revision_after is None
    with Catalogo(config.db_path) as catalogo:
        assert catalogo.obtener_solicitud_descarga("SOL1")["recuperado"] == 1

    PantallaDescargas._revision_automatica(pantalla)
    assert llamadas == [(datos["rfc"], "SOL1")]
    assert programaciones == [True]
