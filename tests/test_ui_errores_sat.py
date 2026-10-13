import queue
from types import SimpleNamespace

import pytest

from conxml.sat.descarga_masiva import ErrorDescargaSAT
from conxml.ui.app import ConXmlApp
from conxml.ui.pantalla_descargas import PantallaDescargas


def preparar_estado_operacion(app, pantalla=None):
    app._pantalla_actual = pantalla
    app._cierre_solicitado = False
    app._estado_operacion = SimpleNamespace(grid=lambda: None, grid_remove=lambda: None)
    app._texto_operacion = SimpleNamespace(configure=lambda **kw: None)
    app._progreso_operacion = SimpleNamespace(
        configure=lambda **kw: None, start=lambda: None, stop=lambda: None, set=lambda valor: None,
    )
    app.winfo_exists = lambda: True


@pytest.mark.parametrize("error,esperado", [
    (ErrorDescargaSAT("Revisa la contraseña de la llave .key."), "Revisa la contraseña"),
    (RuntimeError("detalle interno"), "Consulta el archivo de diagnóstico"),
])
def test_error_sat_muestra_causa_y_restaura_estado(monkeypatch, error, esperado):
    avisos, estados, botones = [], [], []
    monkeypatch.setattr("conxml.ui.pantalla_descargas.messagebox.showerror", lambda *args, **kw: avisos.append(args))
    pantalla = SimpleNamespace(
        _estado_lbl=SimpleNamespace(configure=lambda **kw: estados.append(kw["text"])),
        botones=[SimpleNamespace(configure=lambda **kw: botones.append(kw["state"]))],
    )
    app = SimpleNamespace(
        _ocupada=False, _cola=queue.Queue(), _pantallas={"descargas": pantalla},
        registro=lambda texto: None, after=lambda *args: None, _procesar_cola=lambda: None,
    )
    preparar_estado_operacion(app)
    app._terminar_operacion = lambda: ConXmlApp._terminar_operacion(app)
    # Ejecuta el worker determinísticamente; su resultado se presenta solo al vaciar la cola.
    monkeypatch.setattr("conxml.ui.app.threading.Thread", lambda target, **kw: SimpleNamespace(start=target))
    def trabajo():
        raise error
    assert ConXmlApp.ejecutar(
        app, trabajo, lambda resultado: pytest.fail("No debe presentar éxito"), "SAT",
        al_error=lambda exc: PantallaDescargas._presentar_error(pantalla, exc),
    )
    assert not avisos
    ConXmlApp._procesar_cola(app)
    assert esperado in avisos[0][1]
    assert esperado in estados[-1]
    assert "detalle interno" not in avisos[0][1]
    assert app._ocupada is False
    assert botones == ["disabled", "normal"]


def test_operacion_sin_callback_conserva_error_generico(monkeypatch):
    avisos = []
    monkeypatch.setattr("conxml.ui.app.messagebox.showerror", lambda *args, **kw: avisos.append(args))
    monkeypatch.setattr("conxml.ui.app.threading.Thread", lambda target, **kw: SimpleNamespace(start=target))
    app = SimpleNamespace(
        _ocupada=False, _cola=queue.Queue(), _pantallas={}, registro=lambda texto: None,
        after=lambda *args: None, _procesar_cola=lambda: None,
    )
    preparar_estado_operacion(app)
    app._terminar_operacion = lambda: ConXmlApp._terminar_operacion(app)
    def trabajo():
        raise RuntimeError("detalle interno")
    ConXmlApp.ejecutar(app, trabajo, lambda r: None, "Otra operación")
    ConXmlApp._procesar_cola(app)
    assert "Consulta el archivo de diagnóstico" in avisos[0][1]
    assert "detalle interno" not in avisos[0][1]
    assert app._ocupada is False
