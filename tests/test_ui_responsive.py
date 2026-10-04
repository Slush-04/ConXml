"""Pruebas de geometría adaptable (laptops Mac/Windows) con Tk/CTk reales.

Sin SAT real ni red: solo DB temporal y tablas locales. Cada prueba con
display crea su ventana y la destruye al finalizar; sin display se salta
con mensaje explícito.
"""
from __future__ import annotations

import tkinter as tk
import types
from pathlib import Path

import pytest

from conxml.ui import responsive as resp


def _requiere_ctk():
    try:
        import customtkinter as ctk
    except ImportError:
        pytest.skip("customtkinter no instalado")
    return ctk


def _crear_app(tmp_path, monkeypatch):
    ctk = _requiere_ctk()
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    try:
        raiz = ctk.CTk()
    except tk.TclError:
        pytest.skip("sin display disponible")
    app = None
    try:
        from conxml.ui.app import ConXmlApp

        raiz.update_idletasks()
        app = ConXmlApp(raiz)
        raiz.update_idletasks()
        return raiz, app
    except Exception:
        try:
            raiz.destroy()
        except Exception:
            pass
        raise


def _destruir(raiz):
    try:
        raiz.update_idletasks()
    except Exception:
        pass
    try:
        raiz.destroy()
    except Exception:
        pass


# ── Lógica pura (sin display) ─────────────────────────────────────────────

def test_tamano_inicial_no_excede_pantalla():
    for sw, sh in [(900, 650), (1024, 768), (1366, 768), (1440, 900), (1920, 1080)]:
        for esc in (1.0, 1.25, 1.5):
            w, h = resp.tamano_inicial(sw, sh, esc)
            assert 0 < w <= int(sw / esc - 40) + 1
            assert 0 < h <= int(sh / esc - 60) + 1


def test_umbrales_compacto():
    assert resp.debe_usar_sidebar_compacto(900) is True
    assert resp.debe_usar_sidebar_compacto(1024) is True
    assert resp.debe_usar_sidebar_compacto(1366) is False
    assert resp.debe_usar_modo_baja_altura(650) is True
    assert resp.debe_usar_modo_baja_altura(768) is True
    assert resp.debe_usar_modo_baja_altura(900) is False


# ── Geometría real ────────────────────────────────────────────────────────

def test_geometria_inicial_no_excede_pantalla(tmp_path, monkeypatch):
    ctk = _requiere_ctk()
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    try:
        raiz = ctk.CTk()
    except tk.TclError:
        pytest.skip("sin display disponible")
    try:
        raiz.update_idletasks()
        sw, sh = raiz.winfo_screenwidth(), raiz.winfo_screenheight()
        geo = resp.geometria_inicial(raiz)
        tam = geo.split("+")[0]
        w, h = (int(v) for v in tam.lower().split("x"))
        assert w <= sw
        assert h <= sh
        assert w >= resp.MIN_ANCHO and h >= resp.MIN_ALTO
    finally:
        _destruir(raiz)


def test_sidebar_compacto_y_recuperacion(tmp_path, monkeypatch):
    raiz, app = _crear_app(tmp_path, monkeypatch)
    try:
        app.aplicar_responsive(900, 800)
        raiz.update_idletasks()
        assert app.sidebar_compacto is True
        assert app.ancho_sidebar == resp.ANCHO_SIDEBAR_COMPACTO
        assert app._btn_sidebar.winfo_x() + app._btn_sidebar.winfo_width() <= app._cabecera_lateral.winfo_width()
        assert app._botones["admin40"].cget("text") == "XML 4.0"
        assert app._botones["pagos"].cget("text") == "Pagos"
        # Etiquetas breves legibles, no solo emojis.
        for clave in ("resumen", "admin40", "pagos", "nomina", "ajustes"):
            texto = app._botones[clave].cget("text")
            assert len(texto.strip()) >= 3

        app.aplicar_responsive(1400, 900)
        raiz.update_idletasks()
        assert app.sidebar_compacto is False
        assert app.ancho_sidebar == resp.ANCHO_SIDEBAR
        assert "XML 4.0" in app._botones["admin40"].cget("text")
    finally:
        _destruir(raiz)


def test_sidebar_se_puede_ocultar_y_recuperar(tmp_path, monkeypatch):
    raiz, app = _crear_app(tmp_path, monkeypatch)
    try:
        app.navegar("admin40")
        raiz.geometry("1200x800")
        raiz.update_idletasks()
        assert app._btn_sidebar.winfo_viewable() == 1
        assert app._btn_sidebar.master is app._cabecera_lateral
        ancho_con_sidebar = app._contenido.winfo_width()
        assert app.sidebar_visible is True
        assert app._panel_lateral.winfo_manager() == "grid"

        app.alternar_sidebar()
        raiz.update_idletasks()
        assert app.sidebar_visible is False
        assert app._panel_lateral.winfo_manager() == ""
        assert app._btn_sidebar.winfo_viewable() == 1
        assert app._cabecera_lateral.winfo_viewable() == 1
        assert app._contenido.winfo_width() > ancho_con_sidebar

        app.alternar_sidebar()
        raiz.update_idletasks()
        assert app.sidebar_visible is True
        assert app._panel_lateral.winfo_manager() == "grid"
    finally:
        _destruir(raiz)


def test_selector_clientes_es_ventana_separada_y_abre_contexto(tmp_path, monkeypatch):
    ctk = _requiere_ctk()
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    from conxml.catalog.db import Catalogo
    from conxml.config import Config
    from conxml.ui.app import ConXmlApp, _mostrar_selector_clientes

    ruta_db = Config().db_path
    with Catalogo(ruta_db) as catalogo:
        catalogo.crear_cliente("CLI-01", "Cliente de prueba", "XAXX010101000")

    try:
        raiz = ctk.CTk()
    except tk.TclError:
        pytest.skip("sin display disponible")
    raiz.withdraw()
    try:
        seleccion = []
        selector = _mostrar_selector_clientes(raiz, seleccion.append, ruta_db)
        raiz.update_idletasks()
        assert selector.winfo_exists()
        assert selector.winfo_viewable() == 1
        assert selector.title() == "ConXml — Seleccionar cliente"
        pantalla = selector.winfo_children()[0]
        pantalla._tabla.selection_set("CLI-01")
        pantalla._entrar()
        raiz.update_idletasks()
        assert seleccion == ["CLI-01"]

        app = ConXmlApp(raiz, cliente_actual="CLI-01")
        raiz.update_idletasks()
        assert app._pantalla_actual is app._pantallas["resumen"]
    finally:
        _destruir(raiz)


def test_busqueda_clientes_y_contexto_activo_en_sidebar(tmp_path, monkeypatch):
    ctk = _requiere_ctk()
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    from conxml.catalog.db import Catalogo
    from conxml.config import Config
    from conxml.ui.app import ConXmlApp

    ruta_db = Config().db_path
    with Catalogo(ruta_db) as catalogo:
        catalogo.crear_cliente("CLI-01", "Despacho Norte", "AAA010101AAA")
        catalogo.crear_cliente("CLI-02", "Despacho Sur", "BBB010101BBB")
    try:
        raiz = ctk.CTk()
    except tk.TclError:
        pytest.skip("sin display disponible")
    try:
        app = ConXmlApp(raiz, cliente_actual="CLI-01")
        raiz.update_idletasks()
        assert "Despacho Norte" in app._lbl_cliente.cget("text")

        pantalla = app._pantallas["clientes"]
        pantalla.al_mostrar()
        pantalla._busqueda.set("BBB")
        raiz.update_idletasks()
        filas = pantalla._tabla.get_children()
        assert filas == ("CLI-02",)
        assert pantalla._lbl_conteo.cget("text") == "1 de 2 clientes"
    finally:
        _destruir(raiz)


def test_boveda_busca_carpeta_externa_y_filtra_origen(tmp_path, monkeypatch):
    ctk = _requiere_ctk()
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    from shutil import copy2
    from conxml.boveda import ocultar_instrucciones_boveda
    from conxml.catalog.db import Catalogo
    from conxml.config import Config
    from conxml.ui.app import ConXmlApp

    ruta_db = Config().db_path
    with Catalogo(ruta_db) as catalogo:
        catalogo.crear_cliente("CLI-01", "Cliente de prueba", "EKU9003173C9")
    externa = tmp_path / "externa"
    externa.mkdir()
    copy2(Path(__file__).parent / "fixtures" / "ingreso_iva.xml", externa / "factura.xml")
    ocultar_instrucciones_boveda(Config())

    try:
        raiz = ctk.CTk()
    except tk.TclError:
        pytest.skip("sin display disponible")
    try:
        app = ConXmlApp(raiz, cliente_actual="CLI-01")
        app.navegar("boveda")
        pantalla = app._pantallas["boveda"]
        pantalla._origen.set(str(externa))
        pantalla._origen_externo = True
        pantalla._actualizar_estado_filtros()
        pantalla._actualizar_lista()
        raiz.update_idletasks()
        assert len(pantalla._archivos_actuales) == 1
        assert pantalla._tabla.item(pantalla._tabla.get_children()[0], "values")[0] == "Carpeta"
        # La UI actual conserva editables los filtros de Bóveda; una carpeta
        # externa se lee completa y no debe filtrarse con esos valores.
        assert pantalla._combo_anio.cget("state") == "normal"
        pantalla._anio.set("1900")
        pantalla._mes.set("12")
        pantalla._actualizar_lista()
        assert len(pantalla._archivos_actuales) == 1

        pantalla._direccion.set("Emitidos")
        pantalla._cambiar_origen()
        assert pantalla._combo_anio.cget("state") == "normal"
        assert pantalla._anio.get() == "1900"
        assert pantalla._mes.get() == "12"
    finally:
        _destruir(raiz)


def test_columnas_compartido_con_acciones_y_sin_anadir(tmp_path, monkeypatch):
    raiz, app = _crear_app(tmp_path, monkeypatch)
    try:
        app.navegar("admin40")
        raiz.update_idletasks()
        pantalla = app._pantallas["admin40"]
        assert pantalla._barra_tabla.winfo_manager() == "grid"
        assert set(pantalla._filtros) == {"uuid", "rfc", "serie", "folio"}
        assert pantalla._btn_columnas.winfo_parent() == str(pantalla._marco_acciones)
        assert pantalla._fila_carpeta._btn_secundario is None
        assert pantalla._fila_carpeta._btn_principal.winfo_manager() != ""
        assert pantalla._btn_columnas.winfo_height() <= 32
        assert pantalla._btn_validar.winfo_height() <= 34
        assert pantalla._btn_exportar.winfo_height() <= 34
    finally:
        _destruir(raiz)


def test_baja_altura_oculta_registro_y_colapsa_totales(tmp_path, monkeypatch):
    raiz, app = _crear_app(tmp_path, monkeypatch)
    try:
        app.navegar("admin40")
        raiz.update_idletasks()
        pantalla = app._pantallas["admin40"]
        # Estado amplio: registro visible y totales expandidos.
        app.aplicar_responsive(1400, 950)
        app.mostrar_detalles(True, forzar=True)
        pantalla.fijar_totales_colapsados(False)
        raiz.update_idletasks()
        assert app.detalles_visibles is True
        assert pantalla.totales_colapsados is False

        # Poca altura: se oculta el registro y se colapsan los totales.
        app.aplicar_responsive(1200, 650)
        raiz.update_idletasks()
        assert app.baja_altura is True
        assert app.detalles_visibles is False
        assert pantalla.totales_colapsados is True
        # Controles visibles para volver a mostrar.
        assert app._btn_detalles.winfo_manager() != ""
        assert pantalla._totales_panel._btn_totales.winfo_manager() != ""

        # El usuario puede volver a mostrarlos manualmente.
        app.mostrar_detalles(True)
        pantalla.fijar_totales_colapsados(False)
        raiz.update_idletasks()
        assert app.detalles_visibles is True
        assert pantalla.totales_colapsados is False

        # Operar en poca altura no reabre el registro involuntariamente.
        # Reingresar a compacto desde amplio para reactivar el auto-ocultado.
        app.aplicar_responsive(1400, 950)
        raiz.update_idletasks()
        app.aplicar_responsive(1200, 650)
        raiz.update_idletasks()
        assert app.detalles_visibles is False
        pantalla._mostrar_detalles_operacion()
        raiz.update_idletasks()
        assert app.detalles_visibles is False
        # La operación queda registrada sin reabrir paneles automáticamente.
        assert pantalla._detalles_usados is True
    finally:
        _destruir(raiz)


def test_no_pierde_seleccion_ni_datos_al_redimensionar(tmp_path, monkeypatch):
    raiz, app = _crear_app(tmp_path, monkeypatch)
    try:
        app.navegar("admin40")
        raiz.update_idletasks()
        pantalla = app._pantallas["admin40"]
        tabla = pantalla._tabla
        ncols = len(tabla["columns"])
        for i in range(3):
            tabla.insert("", "end", values=tuple(f"v{i}-{j}" for j in range(ncols)))
        raiz.update_idletasks()
        hijos = list(tabla.get_children())
        tabla.selection_set(hijos[1])
        valores_antes = [tabla.item(h, "values") for h in hijos]
        sel_antes = list(tabla.selection())

        app.aplicar_responsive(900, 650)
        raiz.update_idletasks()
        app.aplicar_responsive(1440, 900)
        raiz.update_idletasks()

        hijos_desp = list(tabla.get_children())
        assert len(hijos_desp) == 3
        assert [tabla.item(h, "values") for h in hijos_desp] == valores_antes
        assert list(tabla.selection()) == sel_antes
    finally:
        _destruir(raiz)


@pytest.mark.parametrize("size", [(900, 650), (1024, 768), (1366, 768), (1440, 900), (1920, 1080)])
@pytest.mark.parametrize("mode", ["admin40", "pagos", "nomina"])
def test_tabla_altura_minima_y_botones_visibles(tmp_path, monkeypatch, size, mode):
    raiz, app = _crear_app(tmp_path, monkeypatch)
    try:
        raiz.geometry(f"{size[0]}x{size[1]}")
        app.navegar(mode)
        app.aplicar_responsive(*size)
        raiz.update_idletasks()
        try:
            raiz.update()
        except Exception:
            pass
        pantalla = app._pantallas[mode]
        tabla = pantalla._tabla
        cont = pantalla._contenedor
        assert tabla.winfo_manager() == "grid"
        assert cont.winfo_width() > 0
        # Tabla con altura útil mínima en modo compacto.
        assert tabla.winfo_height() >= resp.ALTURA_MIN_TABLA
        # Scroll horizontal y vertical presentes.
        assert pantalla._scroll_x.winfo_manager() != ""
        assert pantalla._scroll_y.winfo_manager() != ""
        # Botones dentro del contenedor (no recortados).
        for btn in (pantalla._btn_leer, pantalla._btn_validar,
                    pantalla._btn_exportar, pantalla._btn_columnas):
            x = btn.winfo_rootx() - raiz.winfo_rootx()
            y = btn.winfo_rooty() - raiz.winfo_rooty()
            w = btn.winfo_width()
            assert x >= 0
            assert x + w <= raiz.winfo_width()
            assert 0 <= y and y + btn.winfo_height() <= raiz.winfo_height()
        # Sin compresión: anchos mínimos y fuentes legibles intactos.
        from conxml.ui import theme as th

        assert th.TAM_TABLA >= 10
        for col in list(tabla["columns"])[:10]:
            assert int(tabla.column(col, "width")) >= 60
    finally:
        _destruir(raiz)


def test_selector_vistas_rep_no_empuja_columnas(tmp_path, monkeypatch):
    raiz, app = _crear_app(tmp_path, monkeypatch)
    try:
        app.navegar("pagos")
        raiz.update_idletasks()
        pantalla = app._pantallas["pagos"]
        barra = pantalla._barra_tabla

        app.aplicar_responsive(900, 700)
        raiz.update_idletasks()
        assert pantalla._combo_vista.winfo_manager() != ""
        assert pantalla._seg_vista.winfo_manager() == ""
        col = pantalla._btn_columnas
        assert col.winfo_x() + col.winfo_width() <= barra.winfo_width() + 4

        app.aplicar_responsive(1440, 900)
        raiz.update_idletasks()
        assert pantalla._seg_vista.winfo_manager() != ""
        assert pantalla._combo_vista.winfo_manager() == ""
        assert col.winfo_x() + col.winfo_width() <= barra.winfo_width() + 4
    finally:
        _destruir(raiz)


def test_encabezados_envuelven_y_margenes_compactos(tmp_path, monkeypatch):
    raiz, app = _crear_app(tmp_path, monkeypatch)
    try:
        app.navegar("nomina")
        raiz.update_idletasks()
        pantalla = app._pantallas["nomina"]
        enc = pantalla._encabezado
        assert int(enc._lbl_sub.cget("wraplength")) >= 200
        enc.ajustar_ancho(400)
        assert int(enc._lbl_sub.cget("wraplength")) <= 400

        app.aplicar_responsive(1400, 900)
        raiz.update_idletasks()
        assert int(pantalla._contenedor.pack_info()["padx"]) == 32
        app.aplicar_responsive(900, 650)
        raiz.update_idletasks()
        assert int(pantalla._contenedor.pack_info()["padx"]) == 12
    finally:
        _destruir(raiz)


def test_configure_con_debounce_y_filtrado_hijos(tmp_path, monkeypatch):
    raiz, app = _crear_app(tmp_path, monkeypatch)
    try:
        hijo = app._botones["resumen"]
        # Evento de un hijo: se ignora, sin programar nada.
        app._al_configurar_ventana(types.SimpleNamespace(widget=hijo))
        assert app._resize_after is None
        # Evento de la ventana: se programa con debounce.
        app._al_configurar_ventana(types.SimpleNamespace(widget=app.master))
        assert app._resize_after is not None
        try:
            raiz.after_cancel(app._resize_after)
        except Exception:
            pass
        app._resize_after = None
    finally:
        _destruir(raiz)


@pytest.mark.parametrize("scaling", [1.0, 1.25, 1.5])
def test_tabla_con_escalado_y_detalles_de_operacion(tmp_path, monkeypatch, scaling):
    # Aislar los callbacks globales de CTk de las ventanas de otras pruebas.
    import subprocess
    import sys

    raiz, _ = _crear_app(tmp_path, monkeypatch)
    _destruir(raiz)
    codigo = """
import customtkinter as ctk
from conxml.ui.app import ConXmlApp
from conxml.ui import responsive as resp
ctk.set_widget_scaling(SCALE)
ctk.set_window_scaling(SCALE)
raiz = ctk.CTk()
try:
    app = ConXmlApp(raiz)
    raiz.geometry('900x650')
    app.navegar('admin40')
    raiz.update_idletasks()
    app._aplicar_responsive_inicial()
    raiz.update_idletasks()
    pantalla = app._pantallas['admin40']
    assert app.sidebar_compacto
    pantalla._mostrar_detalles_operacion()
    raiz.update_idletasks()
    assert not app.detalles_visibles
    assert pantalla._resumen.winfo_manager() == ''
    assert pantalla._tabla.winfo_height() / SCALE >= resp.ALTURA_MIN_TABLA
    pantalla.fijar_totales_colapsados(False)
    app.aplicar_responsive(1200, 650)
    app.aplicar_responsive(1000, 650)
    assert not pantalla.totales_colapsados
finally:
    raiz.destroy()
""".replace("SCALE", repr(scaling))
    resultado = subprocess.run([sys.executable, "-c", codigo], capture_output=True,
                               text=True, timeout=30)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
