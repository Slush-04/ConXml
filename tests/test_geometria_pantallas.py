"""Geometría de ventanas en pantallas pequeñas, escaladas y secundarias."""
from types import SimpleNamespace

import pytest

from conxml.ui import responsive as resp


@pytest.mark.parametrize('esc', [1, 1.25, 1.5, 2])
@pytest.mark.parametrize('area', [(0, 0, 1366, 728), (-1920, 40, 1920, 1040), (0, -1080, 1280, 1024)])
def test_dialogo_permanece_en_area_util(esc, area):
    x0, y0, sw, sh = area
    w, h, x, y = resp.calcular_geometria(980, 760, area, esc, (8000, -9000))
    assert x0 <= x <= x0 + sw - w * esc
    assert y0 <= y <= y0 + sh - h * esc
    assert w * esc <= sw - 40 * esc
    assert h * esc <= sh - 60 * esc


def test_dialogo_centrado_sobre_padre():
    assert resp.calcular_geometria(400, 300, (0, 0, 1920, 1080), 1, (700, 500)) == (400, 300, 500, 350)


def test_minimo_dialogo_no_impide_caber_con_dpi_alto(monkeypatch):
    monkeypatch.setattr(resp, 'area_util', lambda _: (-960, 0, 960, 700))
    monkeypatch.setattr(resp, 'escalado_widget', lambda *args, **kwargs: 2)
    padre = SimpleNamespace(winfo_rootx=lambda: -900, winfo_rooty=lambda: 20,
                            winfo_width=lambda: 800, winfo_height=lambda: 650)
    parent = SimpleNamespace(winfo_toplevel=lambda: padre)
    resultado = {}
    dialogo = SimpleNamespace(minsize=lambda w, h: resultado.update(minimo=(w, h)),
                              geometry=lambda value: resultado.update(geometria=value))
    resp.ajustar_dialogo(dialogo, parent, 980, 760, (640, 480))
    assert resultado['minimo'] == (440, 290)
    assert resultado['geometria'].startswith('440x290+-')


def test_fallback_portable(monkeypatch):
    monkeypatch.setattr('sys.platform', 'darwin')
    ventana = SimpleNamespace(winfo_screenwidth=lambda: 1440, winfo_screenheight=lambda: 900)
    assert resp.area_util(ventana) == (0, 0, 1440, 900)
