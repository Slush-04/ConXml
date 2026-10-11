"""Elección inicial de la carpeta de datos, antes de abrir el catálogo."""
import os
import sys
from pathlib import Path
from tkinter import filedialog, messagebox

from conxml.config import Config


def preparar_ubicacion(parent) -> bool:
    config = Config()
    if os.environ.get("CONXML_DATA_DIR") or not getattr(sys, "frozen", False):
        return True
    if config.ubicacion_guardada is not None:
        destino = config.ubicacion_guardada
        if not destino.is_dir():
            messagebox.showerror("Carpeta de datos no disponible",
                                 f"No se encuentra la carpeta:\n{destino}\n\n"
                                 "Conecta la unidad o restaura la carpeta y vuelve a abrir ConXml.", parent=parent)
            return False
        return True
    anterior = config.base
    if anterior.is_dir() and any(anterior.iterdir()):
        # No crear un catálogo vacío para un usuario que ya tiene datos.
        config.guardar_ubicacion(anterior)
        return True
    messagebox.showinfo("Carpeta de datos de ConXml",
                        "Elige dónde guardar los clientes, la bóveda de XML y los respaldos.\n\n"
                        "La ubicación se conservará al actualizar el programa.\n"
                        "Puedes crear una carpeta ConXml en Documentos o en otra unidad.", parent=parent)
    destino = filedialog.askdirectory(title="Elegir carpeta de datos de ConXml",
                                      initialdir=str(Path.home()), mustexist=False, parent=parent)
    if not destino:
        return False
    config.guardar_ubicacion(Path(destino))
    return True
