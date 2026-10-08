"""Verifica que las acciones sigan accesibles al redistribuir las pantallas."""
import tkinter as tk

import customtkinter as ctk
import pytest


@pytest.fixture
def interfaz(tmp_path, monkeypatch):
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    from conxml.catalog.db import Catalogo
    from conxml.config import Config
    from conxml.boveda import ocultar_instrucciones_boveda
    from conxml.ui.app import ConXmlApp
    monkeypatch.setattr("conxml.ui.app.Actualizaciones", lambda app: None)
    with Catalogo(Config().db_path) as cat:
        cat.crear_cliente("DEMO", "Cliente de prueba", "XAXX010101000")
    ocultar_instrucciones_boveda(Config())
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("sin display disponible")
    errores_callback = []
    root.report_callback_exception = lambda *error: errores_callback.append(error)
    app = ConXmlApp(root, cliente_actual="DEMO")
    # Estas pruebas solo verifican presentación; no se lanzan consultas asíncronas.
    monkeypatch.setattr(app, "ejecutar", lambda *args, **kwargs: None)
    yield root, app
    root.destroy()
    assert not errores_callback, errores_callback


@pytest.mark.parametrize("tamano", [(880, 600), (900, 650), (1280, 800)])
def test_controles_no_desbordan_sus_paneles(interfaz, tamano):
    root, app = interfaz
    root.geometry(f"{tamano[0]}x{tamano[1]}")
    app.aplicar_responsive(*tamano)
    for clave in ("clientes", "boveda", "descargas", "admin40", "pagos", "nomina", "ajustes"):
        pantalla = app._pantallas[clave]
        # Evita cargar datos y abrir avisos: aquí importa la geometría.
        for otra in app._pantallas.values():
            otra.place_forget()
        pantalla.place(relwidth=1, relheight=1)
        root.update_idletasks()
        def verificar(widget):
            for hijo in widget.winfo_children():
                if isinstance(hijo, (ctk.CTkButton, ctk.CTkEntry, ctk.CTkComboBox, ctk.CTkCheckBox)) and hijo.winfo_viewable():
                    if clave in ("clientes", "boveda", "admin40", "pagos", "nomina"):
                        assert hijo.winfo_rooty() + hijo.winfo_height() <= root.winfo_rooty() + root.winfo_height(), (clave, hijo, "fuera de la ventana")
                    assert hijo.winfo_x() >= -1, (clave, hijo)
                    assert hijo.winfo_x() + hijo.winfo_width() <= widget.winfo_width() + 2, (clave, hijo, widget.winfo_width())
                verificar(hijo)
        verificar(pantalla)


def test_resumen_vacio_con_metricas_y_accion(interfaz):
    root, app = interfaz
    pantalla = app._pantallas["resumen"]
    pantalla._presentar({"total": 0, "estatus": {"Vigente": 0, "Cancelado": 0, "Sin validar": 0,
                                               "No Encontrado": 0}, "clientes": 1, "errores": 0})
    root.update_idletasks()
    assert len(pantalla._tarjetas_metrica) == 4
    assert all(t.winfo_manager() == "grid" for t in pantalla._tarjetas_metrica)
    assert all(t.lbl_valor.cget("text") == "0" for t in pantalla._tarjetas_metrica)
    assert pantalla._estado.winfo_children()


def test_barra_refluye_y_conserva_controles(interfaz):
    from conxml.ui.widgets import BarraAdaptable, BotonSecundario
    root, app = interfaz
    barra = BarraAdaptable(root, width=500)
    barra.place(x=0, y=0)
    botones = [barra.agregar(BotonSecundario(barra, str(i))) for i in range(4)]
    root.update_idletasks()
    assert len({b.winfo_y() for b in botones}) == 1
    barra.configure(width=260)
    root.update_idletasks()
    assert len({b.winfo_y() for b in botones}) == 2, (barra.winfo_width(), [(b.winfo_reqwidth(), b.winfo_width(), b.winfo_x(), b.winfo_y()) for b in botones], barra._distribucion)
    assert all(b.winfo_y() + b.winfo_height() <= barra.winfo_height() for b in botones)


def test_calendarios_sat_seleccionan_fechas_independientes(interfaz):
    from datetime import date
    from conxml.ui.selector_fecha import SelectorFecha
    root, app = interfaz
    pantalla = app._pantallas["descargas"]
    pantalla.place(relwidth=1, relheight=1)
    root.update_idletasks()
    def selectores(widget):
        for hijo in widget.winfo_children():
            if isinstance(hijo, SelectorFecha):
                yield hijo
            else:
                yield from selectores(hijo)
    desde, hasta = list(selectores(pantalla))
    desde.set("01/03/2024")
    hasta.set("07/10/2026")
    desde._abrir_calendario()
    desde._mover_mes(-1)
    root.update_idletasks()
    assert desde._popup.winfo_viewable()
    boton_29 = next(b for b in desde._marco_dias.winfo_children()
                    if isinstance(b, ctk.CTkButton) and b.cget("text") == "29")
    boton_29.invoke()
    assert pantalla._desde.get() == "29/02/2024"
    assert pantalla._hasta.get() == "07/10/2026"
    assert desde._popup is None
    hasta._abrir_calendario()
    hasta._seleccionar(date(2026, 10, 5))
    assert pantalla._hasta.get() == "05/10/2026"
    assert pantalla._desde.get() == "29/02/2024"
    desde.set("01102026")
    desde._normalizar()
    assert pantalla._desde.get() == "01/10/2026"


def test_solicitud_sat_convierte_fechas_con_barras_y_rechaza_invalidas(interfaz, monkeypatch):
    from datetime import date
    root, app = interfaz
    pantalla = app._pantallas["descargas"]
    avisos, filtros = [], []
    monkeypatch.setattr("conxml.ui.pantalla_descargas.messagebox.showerror", lambda *args, **kw: avisos.append(args))
    monkeypatch.setattr(pantalla, "_credenciales", lambda: ("cer-prueba", "key-prueba", "prueba"))
    monkeypatch.setattr(pantalla, "_presentar_solicitud", lambda cliente, filtro, r, fiel: filtros.append(filtro))
    monkeypatch.setattr(app, "ejecutar", lambda fn, callback, *a, **kw: callback((None, None)))
    pantalla._desde.set("01/09/2026")
    pantalla._hasta.set("07/10/2026")
    pantalla._solicitar()
    assert filtros[0].fecha_inicial == date(2026, 9, 1)
    assert filtros[0].fecha_final == date(2026, 10, 7)
    pantalla._desde.set("31/02/2026")
    pantalla._solicitar()
    assert "DD/MM/AAAA" in avisos[-1][1]
    assert len(filtros) == 1
    pantalla._desde.set("08/10/2026")
    pantalla._solicitar()
    assert "posterior" in avisos[-1][1]
    assert len(filtros) == 1
