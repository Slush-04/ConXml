"""Tests del componente de visibilidad de columnas (conxml.ui.columnas)."""

from conxml.ui.columnas import cargar_ocultas, guardar_ocultas


def test_roundtrip_ocultas(tmp_path):
    guardar_ocultas("demo", ["b", "a"], base=tmp_path)
    assert cargar_ocultas("demo", base=tmp_path) == ["a", "b"]


def test_clave_sin_preferencias_devuelve_vacio(tmp_path):
    assert cargar_ocultas("inexistente", base=tmp_path) == []


def test_json_corrupto_devuelve_vacio(tmp_path):
    ruta = tmp_path / "configuraciones"
    ruta.mkdir()
    (ruta / "columnas_rota.json").write_text("{no es json", encoding="utf-8")
    assert cargar_ocultas("rota", base=tmp_path) == []


def test_sobrescribe_preferencias(tmp_path):
    guardar_ocultas("demo", ["x"], base=tmp_path)
    guardar_ocultas("demo", [], base=tmp_path)
    assert cargar_ocultas("demo", base=tmp_path) == []
