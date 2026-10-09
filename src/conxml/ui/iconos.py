"""Iconos de trazo uniforme, dibujados a alta resolución para pantallas HiDPI."""

import customtkinter as ctk
from PIL import Image, ImageDraw


def icono(nombre: str, color: str, tamano: int = 18) -> ctk.CTkImage:
    escala = 4
    imagen = Image.new("RGBA", (24 * escala, 24 * escala))
    dibujo = ImageDraw.Draw(imagen)

    def linea(puntos):
        dibujo.line([(x * escala, y * escala) for x, y in puntos], fill=color, width=2 * escala, joint="curve")

    def caja(coords):
        dibujo.rounded_rectangle(tuple(n * escala for n in coords), radius=2 * escala,
                                  outline=color, width=2 * escala)

    if nombre == "resumen":
        for x, y in ((3, 3), (14, 3), (3, 14), (14, 14)):
            caja((x, y, x + 7, y + 7))
    elif nombre == "boveda":
        linea([(3, 19), (3, 5), (10, 5), (12, 8), (21, 8), (21, 19), (3, 19)])
    elif nombre == "descargas":
        linea([(12, 3), (12, 15)])
        linea([(7, 10), (12, 15), (17, 10)])
        linea([(4, 16), (4, 21), (20, 21), (20, 16)])
    elif nombre == "pagos":
        linea([(3, 7), (20, 7), (16, 3)])
        linea([(21, 17), (4, 17), (8, 21)])
    elif nombre == "clientes":
        dibujo.ellipse((8*escala, 3*escala, 16*escala, 11*escala), outline=color, width=2*escala)
        linea([(4, 21), (4, 18), (7, 15), (17, 15), (20, 18), (20, 21)])
    elif nombre == "ajustes":
        for y, x in ((5, 8), (12, 16), (19, 10)):
            linea([(3, y), (21, y)])
            dibujo.ellipse(((x-2)*escala, (y-2)*escala, (x+2)*escala, (y+2)*escala), fill=color)
    elif nombre == "columnas":
        caja((3, 4, 21, 20))
        for x in (9, 15):
            linea([(x, 4), (x, 20)])
    elif nombre == "menu":
        for y in (6, 12, 18):
            linea([(4, y), (20, y)])
    else:
        linea([(5, 21), (5, 3), (14, 3), (19, 8), (19, 21), (5, 21)])
        linea([(14, 3), (14, 8), (19, 8)])
        for y in (12, 16):
            linea([(9, y), (15, y)])
    return ctk.CTkImage(light_image=imagen, dark_image=imagen, size=(tamano, tamano))
