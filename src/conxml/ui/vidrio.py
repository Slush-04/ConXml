"""Efectos de vidrio (Liquid Glass / Glassmorphism) para Windows.
Acrílico/Mica via DWM, blending de colores, brillo especular (sheen)."""
from __future__ import annotations

import sys
import tkinter as tk
from typing import Tuple

TRANSPARENTE = "#010203"


def _es_windows() -> bool:
    return sys.platform == "win32"


def _build_number() -> int:
    try:
        return sys.getwindowsversion().build
    except Exception:
        return 0


def _hwnd(ventana: tk.Tk | tk.Toplevel) -> int | None:
    try:
        return ctypes.windll.user32.GetParent(ventana.winfo_id())
    except Exception:
        return None


def _aplicar_dwm_acrilico(hwnd: int) -> bool:
    if _build_number() < 22621:
        return False
    try:
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        DWMSBT_TRANSIENTWINDOW = 2
        valor = ctypes.c_int(DWMSBT_TRANSIENTWINDOW)
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(valor), ctypes.sizeof(valor)
        )
        return res == 0
    except Exception:
        return False


def _aplicar_wca_acrilico(hwnd: int, modo_oscuro: bool) -> bool:
    try:
        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_int),
            ]

        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t),
            ]

        ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
        WCA_ACCENT_POLICY = 19

        if modo_oscuro:
            gradient = 0xD91E1B4B   # índigo-950 semi-opaco
        else:
            gradient = 0xCCF5F3FF   # violeta-50 semi-opaco

        accent = ACCENTPOLICY()
        accent.AccentState = ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 2
        accent.GradientColor = gradient
        accent.AnimationId = 0

        data = WINCOMPATTRDATA()
        data.Attribute = WCA_ACCENT_POLICY
        data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(accent)

        res = ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        return res != 0
    except Exception:
        return False


def _aplicar_modo_oscuro_titulo(hwnd: int, oscuro: bool) -> None:
    try:
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
        valor = ctypes.c_int(1 if oscuro else 0)
        if ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(valor), ctypes.sizeof(valor)
        ) != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1,
                ctypes.byref(valor),
                ctypes.sizeof(valor),
            )
    except Exception:
        pass


def aplicar_efecto(ventana: tk.Tk | tk.Toplevel, modo_oscuro: bool | None = None) -> bool:
    """Activa acrílico/Mica en la ventana. Requiere -transparentcolor ya seteado."""
    if not _es_windows():
        return False
    hwnd = _hwnd(ventana)
    if hwnd is None:
        return False

    if modo_oscuro is None:
        try:
            import customtkinter as ctk
            modo_oscuro = ctk.get_appearance_mode() == "Dark"
        except Exception:
            modo_oscuro = True

    ok = _aplicar_dwm_acrilico(hwnd)
    if not ok:
        ok = _aplicar_wca_acrilico(hwnd, modo_oscuro)

    _aplicar_modo_oscuro_titulo(hwnd, modo_oscuro)
    return ok


def reaplicar_efecto(ventana: tk.Tk | tk.Toplevel, delay_ms: int = 150) -> None:
    """Re-aplica el efecto tras mostrar la ventana (necesario en algunos casos)."""
    if not _es_windows():
        return
    try:
        import customtkinter as ctk
        modo_oscuro = ctk.get_appearance_mode() == "Dark"
    except Exception:
        modo_oscuro = True

    def _reaplicar():
        if ventana.winfo_exists():
            hwnd = _hwnd(ventana)
            if hwnd:
                _aplicar_dwm_acrilico(hwnd) or _aplicar_wca_acrilico(hwnd, modo_oscuro)
                _aplicar_modo_oscuro_titulo(hwnd, modo_oscuro)

    ventana.after(delay_ms, _reaplicar)


def con_alfa(fg: str, alfa: float, fondo: str) -> str:
    """Mezcla fg sobre fondo con alfa [0,1]. Devuelve hex #RRGGBB."""
    fg = fg.lstrip("#")
    fondo = fondo.lstrip("#")
    r1, g1, b1 = int(fg[0:2], 16), int(fg[2:4], 16), int(fg[4:6], 16)
    r2, g2, b2 = int(fondo[0:2], 16), int(fondo[2:4], 16), int(fondo[4:6], 16)
    r = int(r1 * alfa + r2 * (1 - alfa))
    g = int(g1 * alfa + g2 * (1 - alfa))
    b = int(b1 * alfa + b2 * (1 - alfa))
    return f"#{r:02X}{g:02X}{b:02X}"


def _crear_imagen_brillo(alto: int, color_base: str, intensidad: float = 0.45) -> tk.PhotoImage:
    """Crea PhotoImage 1xalto: blanco desvaneciendo hacia color_base."""
    img = tk.PhotoImage(width=1, height=alto)
    r_base, g_base, b_base = int(color_base[1:3], 16), int(color_base[3:5], 16), int(color_base[5:7], 16)
    for y in range(alto):
        t = y / max(1, alto - 1)
        a = intensidad * (1 - t)
        r = int(255 * a + r_base * (1 - a))
        g = int(255 * a + g_base * (1 - a))
        b = int(255 * a + b_base * (1 - a))
        img.put(f"#{r:02X}{g:02X}{b:02X}", to=(0, y))
    return img


class BrilloMixin:
    """Mixin para añadir brillo especular (sheen) en canvas de CTkFrame/CTkButton."""
    _brillo_img: tk.PhotoImage | None = None
    _brillo_id: int | None = None
    _brillo_cache_key: tuple | None = None

    def _actualizar_brillo(self) -> None:
        if not hasattr(self, "_canvas") or not self._canvas.winfo_exists():
            return
        w = self._current_width
        h = self._current_height
        if w <= 1 or h <= 1:
            return
        r = getattr(self, "_corner_radius", 0)
        fg = self._apply_appearance_mode(self._fg_color)
        if fg == "transparent":
            return

        alto = max(8, min(int(h * 0.3), 90))
        ancho = max(1, w - 2 * r)
        key = (ancho, alto, fg)
        if self._brillo_cache_key == key:
            return
        self._brillo_cache_key = key

        img_1px = _crear_imagen_brillo(alto, fg)
        self._brillo_img = img_1px.zoom(ancho, 1)

        if self._brillo_id is not None:
            self._canvas.delete(self._brillo_id)
        self._brillo_id = self._canvas.create_image(
            r, 1, image=self._brillo_img, anchor="nw", tags=("brillo",)
        )
        self._canvas.tag_lower("brillo", "inner_parts")


try:
    import ctypes
except Exception:
    ctypes = None