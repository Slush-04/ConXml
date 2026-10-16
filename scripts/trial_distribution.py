"""Genera la política pública que PyInstaller incorpora en ambos ejecutables."""
import base64
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def generate(source, destination):
    data = json.loads(Path(source).read_text(encoding='utf-8'))
    if set(data) != {'service_url', 'trusted_keys'}:
        raise ValueError('La política admite solo service_url y trusted_keys públicas.')
    parts = urlsplit(data['service_url'])
    if (parts.scheme != 'https' or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.path not in ('', '/') or parts.query or parts.fragment):
        raise ValueError('La edición de prueba exige una URL HTTPS.')
    parts.port
    keys = {}
    for kid, value in data['trusted_keys'].items():
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', kid) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', value):
            raise ValueError('Clave pública o identificador inválidos.')
        raw = base64.urlsafe_b64decode(value + '=')
        if len(raw) != 32 or base64.urlsafe_b64encode(raw).decode().rstrip('=') != value:
            raise ValueError('La clave pública debe tener 32 bytes.')
        keys[kid] = raw
    if not keys:
        raise ValueError('Incluye al menos una clave pública Ed25519.')
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"MODE = 'trial'\nSERVICE_URL = {data['service_url'].rstrip('/')!r}\nTRUSTED_KEYS = {keys!r}\n", encoding='utf-8')
    return str(target.resolve())


def embed_policy(analysis, policy):
    """Actualiza la ruta y el código que PYZ usa del caché de Analysis."""
    from PyInstaller.config import CONF

    module = 'conxml.distribucion'
    if not any(name == module for name, _, _ in analysis.pure):
        raise RuntimeError('No se encontró la política de distribución; compilación abortada.')
    # El caché de PyInstaller se asocia al id de esta lista. Conservar la lista
    # evita que su id se reutilice entre los dos Analysis y mezcle sus cachés.
    analysis.pure[:] = [(name, policy if name == module else path, kind)
                        for name, path, kind in analysis.pure]
    cache = CONF['code_cache'].get(id(analysis.pure))
    if cache is not None:
        cache[module] = compile(Path(policy).read_text(encoding='utf-8'), policy, 'exec')


def verify_archive(archive_path, policy):
    """Comprobar el código del PYZ generado, antes de crear el ejecutable."""
    import runpy
    from PyInstaller.archive.readers import ZlibArchiveReader

    expected = runpy.run_path(policy)
    actual = {}
    code = ZlibArchiveReader(str(archive_path)).extract('conxml.distribucion')
    if code is None:
        raise RuntimeError('El archivo empaquetado no contiene la política de prueba.')
    exec(code, actual)
    if any(actual.get(key) != expected[key] for key in ('MODE', 'SERVICE_URL', 'TRUSTED_KEYS')):
        raise RuntimeError('La política empaquetada no corresponde a la edición de prueba; compilación abortada.')
