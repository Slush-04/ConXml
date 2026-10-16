"""Política incluida en el paquete. No se lee desde datos, backups ni variables de entorno.

Las ediciones anteriores y la edición de desarrollo quedan exentas. Para distribuir
una prueba se cambia MODE, SERVICE_URL y TRUSTED_KEYS en el proceso de compilación.
Una prueba mal configurada falla cerrada; nunca vuelve al modo de desarrollo.
"""
MODE = 'development'
SERVICE_URL = ''
TRUSTED_KEYS: dict[str, bytes] = {}
