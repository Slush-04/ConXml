"""Inicio por cliente sin red y protección contra respuestas tardías."""
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk

import customtkinter as ctk
import pytest

from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpeta
from conxml.ui.pantalla_resumen import PantallaResumen
from conxml.ui import theme as th


@pytest.fixture
def inicio(tmp_path):
    th.configurar_ctk()
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("sin display disponible")
    errores = []
    root.report_callback_exception = lambda *args: errores.append(args)
    llamadas, rutas = [], []
    app = SimpleNamespace(
        db_path=tmp_path / "catalogo.db", cliente_actual="A", _ocupada=False,
        cambiar_cliente=lambda: rutas.append("clientes"), navegar=rutas.append,
        ejecutar=lambda fn, cb, *a, **kw: llamadas.append((fn, cb, kw)),
    )
    with Catalogo(app.db_path) as cat:
        importar_carpeta(cat, Path(__file__).parent / "fixtures", "A")
        cat.crear_cliente("B", "Cliente B")
    pantalla = PantallaResumen(root, app)
    pantalla.pack(fill="both", expand=True)
    yield root, pantalla, app, llamadas, rutas
    root.destroy()
    assert not errores


def test_cambiar_cliente_descarta_respuesta_anterior(inicio):
    root, pantalla, app, llamadas, _ = inicio
    pantalla.al_mostrar()
    leer_a, mostrar_a, _ = llamadas[-1]
    datos_a = leer_a()
    app.cliente_actual = "B"
    pantalla.al_mostrar()
    mostrar_a(datos_a)
    assert all(t.lbl_valor.cget("text") == "—" for t in pantalla._tarjetas_metrica)
    leer_b, mostrar_b, _ = llamadas[-1]
    mostrar_b(leer_b())
    assert all(t.lbl_valor.cget("text") == "0" for t in pantalla._tarjetas_metrica)
    assert "Cliente B" in pantalla._encabezado._lbl_sub.cget("text")


@pytest.mark.parametrize("ancho,alto", [(700, 600), (1080, 800)])
def test_inicio_adapta_tarjetas_y_ayuda_funciona(inicio, ancho, alto):
    root, pantalla, app, llamadas, rutas = inicio
    root.geometry(f"{ancho}x{alto}")
    pantalla.al_mostrar()
    leer, mostrar, _ = llamadas[-1]
    mostrar(leer())
    root.update()
    for tarjeta in pantalla._tarjetas_accion + pantalla._tarjetas_metrica:
        assert tarjeta.winfo_x() >= 0
        assert tarjeta.winfo_x() + tarjeta.winfo_width() <= tarjeta.master.winfo_width() + 2
    boton, detalle = pantalla._ayudas[0]
    assert not detalle.winfo_manager()
    boton.invoke()
    root.update_idletasks()
    assert detalle.winfo_manager() == "pack"
    boton.invoke()
    assert not detalle.winfo_manager()
    for tarjeta, destino in zip(pantalla._tarjetas_accion, ("boveda", "descargas", "admin40", "pagos", "nomina", "ajustes")):
        tarjeta._boton.invoke()
        assert rutas[-1] == destino
    assert pantalla._contenedor._parent_canvas.yview()[1] < 1.0


def test_inicio_ocupado_no_lanza_otra_operacion(inicio):
    _, pantalla, app, llamadas, _ = inicio
    app._ocupada = True
    pantalla.al_mostrar()
    assert llamadas == []
    assert "operación en curso" in pantalla._actualizado.cget("text")


def test_inicio_muestra_error_y_permite_reintentar(inicio):
    _, pantalla, _, llamadas, _ = inicio
    pantalla.al_mostrar()
    llamadas[-1][2]["al_error"](ValueError("prueba"))
    assert "reintentar" in pantalla._actualizado.cget("text")
    pantalla._btn_actualizar.invoke()
    assert len(llamadas) == 2


def test_inicio_redimensiona_y_desplaza_sin_perder_datos(inicio):
    root, pantalla, _, llamadas, _ = inicio
    pantalla.al_mostrar()
    leer, mostrar, _ = llamadas[-1]
    mostrar(leer())
    tarjetas = list(pantalla._tarjetas_metrica)
    for ancho in (1080, 700, 1080):
        root.geometry(f"{ancho}x650")
        root.update()
        assert pantalla._tarjetas_metrica == tarjetas
        assert tarjetas[0].lbl_valor.cget("text") == "8"
        assert pantalla._contenedor.winfo_manager() == "canvas"
    canvas = pantalla._contenedor._parent_canvas
    canvas.yview_moveto(1)
    root.update()
    assert canvas.yview()[0] > 0
    assert pantalla._barra_scroll.get() == canvas.yview()


def test_sin_cliente_no_acumula_avisos(inicio):
    _, pantalla, app, llamadas, rutas = inicio
    app.cliente_actual = None
    pantalla.al_mostrar()
    pantalla.actualizar_metricas()
    assert llamadas == []
    assert len(pantalla._estado.winfo_children()) == 1
