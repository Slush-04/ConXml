"""Utilidades de geometría adaptable para laptops Mac y Windows.

Funciones puras (sin display) + helpers con APIs públicas de Tk/CTk.
No usa zoom dependiente de Windows ni rutas privadas de CustomTkinter.
"""
from __future__ import annotations


# ── Umbrales y mínimos ────────────────────────────────────────────────────
ANCHO_SIDEBAR = 240
ANCHO_SIDEBAR_COMPACTO = 140

# Ventana estrecha -> sidebar compacto + selector REP en ComboBox.
UMBRAL_ANCHO_COMPACTO = 1100
# Poca altura -> ocultar registro y colapsar totales para dar sitio a la tabla.
UMBRAL_ALTURA_COMPACTA = 800

# Altura mínima útil de la tabla en modo compacto (criterio: >= 150px).
ALTURA_MIN_TABLA = 150

# Tamaño mínimo práctico para laptop (menor que 900x650 para no recortar).
MIN_ANCHO = 880
MIN_ALTO = 600

# Tamaño inicial según el espacio disponible de pantalla (en unidades lógicas).
ANCHO_INICIAL_OBJETIVO = 1280
ALTO_INICIAL_OBJETIVO = 800
ANCHO_INICIAL_MIN = 900
ALTO_INICIAL_MIN = 620

# Retardo del debounce del evento Configure (ms).
RETARDO_DEBOUNCE_MS = 120


def escalado_widget(widget=None, ventana=False) -> float:
    """Escalado CustomTkinter por API pública (1.0 si no disponible)."""
    try:
        import customtkinter as ctk

        if widget is not None:
            getter = (ctk.ScalingTracker.get_window_scaling if ventana
                      else ctk.ScalingTracker.get_widget_scaling)
            valor = float(getter(widget))
            if valor > 0:
                return valor
    except Exception:
        pass
    return 1.0


def tamano_inicial(ancho_pantalla: int, alto_pantalla: int, escalado: float = 1.0) -> tuple[int, int]:
    """Calcula el tamaño inicial lógico sin exceder la pantalla.

    Usa casi todo el espacio lógico (pantalla / escalado), recortado a
    lo disponible menos un margen para bordes/dock.
    Función pura: no necesita display y es la que cubren las pruebas.
    """
    esc = float(escalado) if escalado and escalado > 0 else 1.0
    try:
        sw = int(ancho_pantalla)
    except Exception:
        sw = 1280
    try:
        sh = int(alto_pantalla)
    except Exception:
        sh = 800
    if sw <= 0:
        sw = 1280
    if sh <= 0:
        sh = 800

    sw_log = sw / esc
    sh_log = sh / esc

    # En monitores amplios usamos más espacio desde el arranque. El límite
    # anterior de 1366 px dejaba grandes franjas vacías en pantallas modernas;
    # macOS tampoco aplica de forma consistente el estado Tk "zoomed".
    w = int(max(ANCHO_INICIAL_MIN, sw_log * 0.96))
    h = int(max(ALTO_INICIAL_MIN, sh_log * 0.94))

    # Margen lógico para bordes del SO / dock / barra de tareas.
    max_w = max(1, int(sw_log - 40))
    max_h = max(1, int(sh_log - 60))
    w = min(w, max_w)
    h = min(h, max_h)

    # En pantallas pequeñas conservamos un tamaño manejable; en las amplias
    # dejamos que la interfaz ocupe casi toda el área útil.
    w = min(w, max_w)
    h = min(h, max_h)
    return (w, h)


def debe_usar_sidebar_compacto(ancho_ventana: int) -> bool:
    """True si la ventana es estrecha y conviene el sidebar compacto."""
    try:
        return int(ancho_ventana) < UMBRAL_ANCHO_COMPACTO
    except Exception:
        return False


def debe_usar_modo_baja_altura(alto_ventana: int) -> bool:
    """True si hay poca altura y conviene colapsar totales/registro."""
    try:
        return int(alto_ventana) < UMBRAL_ALTURA_COMPACTA
    except Exception:
        return False


def area_util(ventana) -> tuple[int, int, int, int]:
    """Área disponible (x, y, ancho, alto) en coordenadas de Tk.

    Windows usa el monitor del padre y excluye la barra de tareas. Tk no
    expone el área de trabajo por monitor en las demás plataformas: allí
    usamos su pantalla y reservamos márgenes al dimensionar las ventanas.
    """
    import sys

    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class InfoMonitor(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                            ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

            usuario = ctypes.windll.user32
            usuario.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
            usuario.MonitorFromWindow.restype = wintypes.HANDLE
            usuario.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(InfoMonitor)]
            usuario.GetMonitorInfoW.restype = wintypes.BOOL
            monitor = usuario.MonitorFromWindow(ventana.winfo_toplevel().winfo_id(), 2)
            info = InfoMonitor()
            info.cbSize = ctypes.sizeof(info)
            if usuario.GetMonitorInfoW(monitor, ctypes.byref(info)):
                r = info.rcWork
                return r.left, r.top, r.right - r.left, r.bottom - r.top
        except (AttributeError, OSError, TypeError, ValueError):
            pass
    try:
        return (0, 0, max(1, int(ventana.winfo_screenwidth())),
                max(1, int(ventana.winfo_screenheight())))
    except (AttributeError, TypeError, ValueError):
        return 0, 0, 1280, 800


def calcular_geometria(ancho: int, alto: int, area: tuple[int, int, int, int],
                       escalado: float = 1.0, centro=None) -> tuple[int, int, int, int]:
    """Limita un tamaño lógico y centra sus píxeles dentro del área útil.

    El margen reserva espacio para las decoraciones del sistema. Las
    coordenadas conservan el signo para monitores a la izquierda del principal.
    """
    esc = float(escalado) if escalado and escalado > 0 else 1.0
    ax, ay, aw, ah = area
    w = min(max(1, int(ancho)), max(1, int(aw / esc - 40)))
    h = min(max(1, int(alto)), max(1, int(ah / esc - 60)))
    cx, cy = centro if centro is not None else (ax + aw / 2, ay + ah / 2)
    x = round(max(ax, min(cx - w * esc / 2, ax + aw - w * esc)))
    y = round(max(ay, min(cy - h * esc / 2, ay + ah - h * esc - 30 * esc)))
    return w, h, x, y


def ajustar_dialogo(dialogo, parent, ancho: int, alto: int,
                    minimo: tuple[int, int]) -> None:
    """Centra un diálogo y reduce su mínimo si la pantalla no lo admite."""
    padre = parent.winfo_toplevel()
    area = area_util(padre)
    esc = escalado_widget(dialogo, ventana=True)
    centro = (padre.winfo_rootx() + padre.winfo_width() / 2,
              padre.winfo_rooty() + padre.winfo_height() / 2)
    w, h, x, y = calcular_geometria(ancho, alto, area, esc, centro)
    dialogo.minsize(min(minimo[0], w), min(minimo[1], h))
    dialogo.geometry(f"{w}x{h}+{x}+{y}")


def geometria_inicial(raiz) -> str:
    """Geometría inicial centrada y contenida en el área de trabajo."""
    area = area_util(raiz)
    esc = escalado_widget(raiz, ventana=True)
    w, h = tamano_inicial(area[2], area[3], esc)
    w, h, x, y = calcular_geometria(w, h, area, esc)
    return f"{w}x{h}+{x}+{y}"
