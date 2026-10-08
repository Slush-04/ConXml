import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from conxml import estado_local
from conxml.boveda import seleccionar_xmls
from conxml.catalog.db import Catalogo
from conxml.config import Config
from conxml.sat.almacenamiento import guardar_paquete
from conxml.sat.descarga_masiva import RespuestaSAT
from conxml.ui.pantalla_descargas import PantallaDescargas


def paquete_xml():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archivo:
        archivo.writestr("factura.xml", (Path(__file__).parent / "fixtures/ingreso_iva.xml").read_bytes())
    return stream.getvalue()


def test_preferencias_destino_conservan_sesion_y_boveda_en_modo_zip(tmp_path, monkeypatch):
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    estado_local.guardar({"sesion": {"cliente": "C1"}})
    estado_local.guardar({"descargas_sat": {"modo": "zip", "carpeta_xml": str(tmp_path / "xml"), "carpeta_zip": str(tmp_path / "zip")}})
    assert estado_local.cargar()["sesion"]["cliente"] == "C1"
    assert Config().modo_descarga_sat == "zip"
    assert Config().carpeta_boveda == tmp_path / "xml"
    assert Config().carpeta_zip_sat == tmp_path / "zip"


def test_zip_conserva_bytes_sin_extraer(tmp_path, monkeypatch):
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("conxml.sat.almacenamiento.guardar_paquete_zip", lambda *args: pytest.fail("No debe extraer ZIP"))
    contenido = paquete_xml()
    resultado = guardar_paquete(contenido, Config(), "C1", "RFC", "SOL1", "P1", modo="zip")
    assert resultado.zip_guardado.read_bytes() == contenido
    assert resultado.archivos == []
    assert not list(tmp_path.rglob("*.xml"))
    assert not Config().carpeta_boveda.exists()


@pytest.mark.parametrize("rfc,direccion", [("EKU9003173C9", "Emitidos"), ("COSC8001137NA", "Recibidos")])
def test_xml_organizado_en_raiz_elegida_visible_en_boveda(tmp_path, monkeypatch, rfc, direccion):
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path / "datos"))
    raiz = tmp_path / "destino"
    estado_local.guardar({"descargas_sat": {"carpeta_xml": str(raiz)}})
    resultado = guardar_paquete(paquete_xml(), Config(), "C1", rfc, "SOL1", "P1", modo="organizado")
    assert resultado.copiados == 1
    assert resultado.errores == 0
    assert resultado.archivos == [raiz / "C1" / direccion / "2024" / "02" / "factura.xml"]
    assert seleccionar_xmls(Config(), "C1", direccion, "2024", "02") == resultado.archivos
    assert resultado.zip_guardado is None


@pytest.mark.parametrize("modo", ["zip", "organizado"])
def test_recuperacion_sat_importa_solo_modo_organizado(tmp_path, monkeypatch, modo):
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    estado_local.guardar({"descargas_sat": {"modo": modo}})
    with Catalogo(Config().db_path) as cat:
        cat.guardar_solicitud_descarga(cliente="C1", rfc="EKU9003173C9", direccion="Emitidos", fecha_inicial="2024-02-01", fecha_final="2024-02-29", tipo_comprobante="", id_sat="SOL1", cod_estatus="5000", estado=1, mensaje="Aceptada")
    descargas = []
    class SAT:
        def __init__(self, fiel): pass
        def verificar(self, *args):
            return RespuestaSAT(estado=3, cod_estatus="5000", paquetes=["P1"], numero_cfdis=1)
        def descargar_paquete(self, *args):
            descargas.append(args)
            return paquete_xml()
        def cerrar(self): pass
    monkeypatch.setattr("conxml.ui.pantalla_descargas.CredencialEFirma.cargar", lambda *args: SimpleNamespace(rfc="EKU9003173C9"))
    monkeypatch.setattr("conxml.ui.pantalla_descargas.ClienteDescargaSAT", SAT)
    if modo == "zip":
        monkeypatch.setattr("conxml.sat.seguimiento.importar_carpetas", lambda *args: pytest.fail("ZIP no debe importar al catálogo"))
    resultados = []
    app = SimpleNamespace(db_path=Config().db_path, ejecutar=lambda trabajo, presentar, texto, **kwargs: presentar(trabajo()), actualizar_resumen=lambda: None, _pantallas={})
    pantalla = SimpleNamespace(
        app=app, _tabla=SimpleNamespace(selection=lambda: ["SOL1"]),
        _credenciales=lambda: ("cert", "key", "secret"), _datos_cliente=lambda: ("C1", "EKU9003173C9"),
        _estado_lbl=SimpleNamespace(configure=lambda **kw: None), _password=SimpleNamespace(set=lambda valor: None),
        _renderizar_historial=lambda filas: None,
        _presentar_error=lambda error: pytest.fail(str(error)),
        _guardar_firma=lambda fiel: None,
    )
    def presentar(datos, resultado):
        resultados.append(resultado)
        PantallaDescargas._presentar_verificacion(pantalla, datos, resultado)
    pantalla._presentar_verificacion = presentar
    PantallaDescargas._verificar(pantalla)
    assert resultados[0].recuperada is True
    with Catalogo(Config().db_path) as cat:
        assert cat.contar("comprobantes") == (1 if modo == "organizado" else 0)
        fila = cat.obtener_solicitud_descarga("SOL1")
        assert fila["recuperado"] == 1
        mensaje = fila["mensaje"]
        assert ("ZIP sin extraer" if modo == "zip" else "XML organizados") in mensaje
    # Cambiar el modo no reenvía ni vuelve a recuperar una solicitud guardada.
    estado_local.guardar({"descargas_sat": {"modo": "zip" if modo == "organizado" else "organizado"}})
    PantallaDescargas._verificar(pantalla)
    assert len(descargas) == 1
    with Catalogo(Config().db_path) as cat:
        assert cat.obtener_solicitud_descarga("SOL1")["mensaje"] == mensaje
