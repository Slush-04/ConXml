"""Acceso manual al portal oficial; la integración automática está pendiente."""
from __future__ import annotations

import webbrowser

PORTAL_CFDI_URL = "https://portalcfdi.facturaelectronica.sat.gob.mx/"
INFORMACION_DESCARGA_URL = (
    "https://wwwmatnp.sat.gob.mx/consultas/42968/"
    "consulta-y-recuperacion-de-comprobantes-(nuevo)"
)


def abrir_portal_sat() -> bool:
    """Abre el navegador del usuario sin recibir ni guardar credenciales.

    El resultado indica si el sistema aceptó abrir el navegador, no si el SAT
    está disponible. Los errores del navegador los presenta la interfaz.
    """
    return webbrowser.open(PORTAL_CFDI_URL, new=2)
