from pathlib import Path
import shutil

from conxml.boveda import (
    copiar_xmls,
    etiqueta_mes,
    inicializar_boveda,
    instrucciones_boveda_ocultas,
    ocultar_instrucciones_boveda,
    periodos_disponibles,
    procesar_masivo,
    seleccionar_xmls,
)
from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpetas
from conxml.config import Config

FIXTURES = Path(__file__).parent / "fixtures"


def test_copia_xml_organizada_por_direccion_y_periodo(tmp_path, monkeypatch):
    origen = tmp_path / "origen"
    origen.mkdir()
    shutil.copy2(FIXTURES / "ingreso_iva.xml", origen / "factura.xml")
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    config = Config()
    resultado = copiar_xmls(origen, config, "CLI-1", "EKU9003173C9")
    assert resultado.copiados == 1
    ruta = tmp_path / "boveda" / "CLI-1" / "Emitidos" / "2024" / "02" / "factura.xml"
    # El test usa una instancia normal con CONXML_DATA_DIR fijada abajo.
    assert ruta.is_file()
    assert seleccionar_xmls(config, "CLI-1", "Emitidos", "2024", "02") == [ruta]
    assert periodos_disponibles(config, "CLI-1") == (["2024"], ["02"])

    with Catalogo(tmp_path / "catalogo.db") as catalogo:
        carga = importar_carpetas(catalogo, [ruta], "CLI-1", limpiar_antes=True)
        assert carga.insertados == 1


def test_boveda_solo_crea_direcciones_y_migra_masivo_anterior(tmp_path, monkeypatch):
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    config = Config()
    raiz = inicializar_boveda(config, "CLI-1")
    assert sorted(p.name for p in raiz.iterdir()) == ["Emitidos", "Recibidos"]

    (raiz / "Emitidos" / "Masivo").mkdir()
    shutil.copy2(FIXTURES / "ingreso_iva.xml", raiz / "Emitidos" / "Masivo" / "pendiente.xml")
    assert seleccionar_xmls(config, "CLI-1") == []
    assert seleccionar_xmls(config, "CLI-1", "Masivo") == []
    resultado = procesar_masivo(config, "CLI-1", "EKU9003173C9")
    assert resultado.copiados == 1
    assert len(seleccionar_xmls(config, "CLI-1", "Emitidos", "2024", "02")) == 1
    assert not (raiz / "Emitidos" / "Masivo").exists()
    assert etiqueta_mes("09") == "09-Sep"
    assert etiqueta_mes("10") == "10-Oct"


def test_preferencia_de_instrucciones_boveda(tmp_path, monkeypatch):
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    config = Config()
    assert instrucciones_boveda_ocultas(config) is False
    ocultar_instrucciones_boveda(config)
    assert instrucciones_boveda_ocultas(config) is True
