"""Activación cloud y reloj anclado. Estado privado separado de los datos fiscales."""
from __future__ import annotations

import atexit
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import secrets
import threading
import time
from uuid import uuid4

import keyring
import requests

from conxml import __version__, distribucion
from conxml.config import Config
from conxml.licencias import LicenseError, verify_lease
from conxml.monitoreo import save_record, validate_url, MonitoringError

SERVICE = 'ConXml-Licensing-v1'
MAX_RESPONSE = 16384


def private_dir():
    return Config().ubicacion_path.parent.parent / '.conxml-licensing'


def request_json(url, path, payload=None, token=None, *, limit=MAX_RESPONSE):
    """Transporte sin redirects, errores privados y límite también al descomprimir."""
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with requests.request('GET' if payload is None else 'POST', url + path,
                              json=payload, headers=headers, timeout=(3, 7),
                              allow_redirects=False, stream=True) as response:
            if response.status_code == 429:
                retry = response.headers.get('Retry-After', '')
                seconds = int(retry) if retry.isdigit() else 300
                raise RetryLater(max(60, seconds))
            if response.status_code not in (200, 201):
                raise LicenseError('El servicio no aceptó la solicitud. Revisa la credencial o intenta más tarde.')
            raw = bytearray()
            deadline = time.monotonic() + 15
            for chunk in response.iter_content(4096):
                raw.extend(chunk)
                if len(raw) > limit or time.monotonic() > deadline:
                    raise ValueError()
            result = json.loads(raw)
            if not isinstance(result, dict) or result.get('schema') != 1:
                raise ValueError()
            return result
    except (requests.RequestException, ValueError, TypeError, OSError):
        raise LicenseError('No se pudo validar la licencia. Revisa la conexión e intenta nuevamente.') from None


class RetryLater(LicenseError):
    def __init__(self, seconds):
        self.seconds = seconds
        super().__init__('El servicio solicita esperar antes de reintentar.')


class InstallationLock:
    """Una sesión por instalación: un proceso antiguo no puede informar otro cierre."""
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = path.open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.stream.seek(0)
                self.stream.write(b'0')
                self.stream.flush()
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise LicenseError('ConXml ya está abierto o hay una tarea de esta instalación en curso.') from None

    def close(self):
        if not self.stream.closed:
            self.stream.close()


class LicenseClient:
    def __init__(self, *, mode=None, url=None, keys=None, directory=None, vault=keyring,
                 wall=time.time, monotonic=time.monotonic):
        self.mode = distribucion.MODE if mode is None else mode
        self.required = self.mode != 'development'
        self.url = distribucion.SERVICE_URL if url is None else url
        self.keys = distribucion.TRUSTED_KEYS if keys is None else keys
        self.directory = Path(directory) if directory else private_dir()
        self.vault, self.wall, self.monotonic = vault, wall, monotonic
        self.mutex = threading.RLock()
        self.sync_mutex = threading.Lock()
        self.lease = None
        self.error = 'Activación pendiente. Introduce tu código de prueba.'
        self.next_attempt = 0
        self.failures = 0
        self.anchor = None
        self.record = None
        self.stopped = threading.Event()
        self.worker = None
        self.process_lock = None
        self.broken = False
        if not self.required:
            return
        if self.mode != 'trial':
            raise LicenseError('Modo de distribución desconocido.')
        try:
            self.url = validate_url(self.url)
        except MonitoringError:
            raise LicenseError('Esta edición de prueba no tiene un servicio válido incluido.') from None
        if not self.url.startswith('https://') or not self.keys or any(
                not isinstance(v, bytes) or len(v) != 32 for v in self.keys.values()):
            raise LicenseError('Esta edición de prueba no tiene URL HTTPS y claves públicas válidas.')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.process_lock = InstallationLock(self.directory / 'session.lock')
        try:
            self._load()
        except Exception:
            self.process_lock.close()
            raise
        atexit.register(self.close)

    def _load(self):
        try:
            raw = self.vault.get_password(SERVICE, 'installation')
            if raw is None:
                if (self.directory / 'lease.json').exists():
                    raise ValueError()
                # UUID y token se escriben juntos antes de la primera petición.
                self.record = {'device_id': str(uuid4()), 'token': secrets.token_urlsafe(32),
                               'revisions': {}, 'last_wall': 0, 'trusted_now': 0, 'lease': None, 'url': self.url}
                self._persist()
            else:
                self.record = json.loads(raw)
                from conxml.licencias import _uuid
                _uuid(self.record['device_id'])
                if (not re.fullmatch(r'[A-Za-z0-9_-]{43}', self.record['token'])
                        or self.record['url'] != self.url
                        or not isinstance(self.record['revisions'], dict)
                        or type(self.record['last_wall']) not in (int, float)
                        or not math.isfinite(self.record['last_wall'])
                        or type(self.record['trusted_now']) not in (int, float)
                        or not math.isfinite(self.record['trusted_now'])):
                    raise ValueError()
                if len(self.record['revisions']) > 100:
                    raise ValueError()
                for identifier, revisions in self.record['revisions'].items():
                    _uuid(identifier)
                    if (not isinstance(revisions, list) or len(revisions) != 2
                            or any(type(v) is not int or not 0 <= v <= 2**53 - 1 for v in revisions)):
                        raise ValueError()
                if (self.record['last_wall'] < 0 or self.record['trusted_now'] < 0
                        or self.record['lease'] is not None and not isinstance(self.record['lease'], str)):
                    raise ValueError()
                if self.record['lease']:
                    self.lease = self._verify(self.record['lease'])
                    if self.record['trusted_now'] < self.lease.issued_at:
                        raise ValueError()
                    now = self.wall()
                    saved = self.record['last_wall']
                    if now + 5 < saved or now + 300 < self.lease.issued_at:
                        self.error = 'El reloj retrocedió. Conecta para validar la licencia.'
                    else:
                        self.anchor = (max(now, saved, self.record['trusted_now'] + 30, self.lease.issued_at), self.monotonic())
                self._check_journal()
        except Exception:
            raise LicenseError('No se pudo leer la identidad o licencia del almacén seguro. Contacta al administrador; no se creó otra identidad.') from None

    def _check_journal(self):
        # Write-ahead: una denegación no se pierde si el keyring falla después
        # de recibirla. Un archivo nunca concede permisos por sí solo.
        try:
            with (self.directory / 'lease.json').open('rb') as stream:
                raw = stream.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise ValueError()
            compact = json.loads(raw)['lease']
            candidate = self._verify(compact)
            if compact == self.record['lease']:
                return
            self.record['revisions'][candidate.license_id] = [candidate.license_revision, candidate.device_revision]
        except FileNotFoundError:
            if self.record['lease'] is None:
                return
        except (OSError, ValueError, TypeError, KeyError, LicenseError):
            pass
        self.anchor = None
        self.error = 'La caché está dañada o hay una validación pendiente de guardar. Conecta para validar la licencia.'

    def _persist(self):
        try:
            self.vault.set_password(SERVICE, 'installation', json.dumps(self.record))
        except Exception:
            self.broken = True
            self.anchor = None
            raise LicenseError('No se pudo guardar el estado de licencia en el almacén seguro.') from None

    def _verify(self, compact, nonce=None):
        lease = verify_lease(compact, self.keys, device_id=self.record['device_id'], expected_nonce=nonce)
        revisions = self.record['revisions'].get(lease.license_id, [0, 0])
        return verify_lease(compact, self.keys, device_id=self.record['device_id'], expected_nonce=nonce,
                            minimum_license_revision=revisions[0], minimum_device_revision=revisions[1])

    def allowed(self):
        if not self.required:
            return True
        with self.mutex:
            if self.broken or self.anchor is None or self.lease is None:
                return False
            now = max(self.anchor[0] + self.monotonic() - self.anchor[1], self.wall())
            if self.wall() + 5 < self.record['last_wall']:
                self.anchor = None
                self.error = 'El reloj retrocedió. Conecta para validar la licencia.'
                return False
            if now >= self.record['trusted_now'] + 30:
                self.record['last_wall'] = self.wall()
                self.record['trusted_now'] = now
                try:
                    self._persist()
                except LicenseError as exc:
                    self.error = str(exc)
                    return False
            permitted = self.lease.permits_use(int(now))
            if not permitted:
                self.error = {'blocked': 'Licencia o equipo bloqueado.', 'revoked': 'Licencia revocada.',
                              'expired': 'La prueba ha vencido.'}.get(self.lease.status,
                              'Validación vencida. Conecta para renovar el permiso.')
            return permitted

    def require(self):
        # Ambos controles deben permitir el acceso; una licencia no borra un
        # bloqueo previo del monitor directo, incluso si se desactiva el reporte.
        from conxml.monitoreo import config_path, read_record, validate_record, ControlState
        try:
            path = config_path()
            if path.exists() and ControlState(validate_record(read_record(path))).blocked:
                raise LicenseError('Acceso suspendido por el administrador del monitor directo.')
        except MonitoringError:
            raise LicenseError('No se pudo validar el control del monitor directo.') from None
        if not self.allowed():
            raise LicenseError(self.error)

    def sync(self, code=None):
        if not self.required:
            return
        with self.sync_mutex:
            if self.monotonic() < self.next_attempt:
                raise LicenseError('Espera antes de reintentar la validación.')
            if code is not None and not re.fullmatch(r'[A-Za-z0-9_-]{43}', code):
                raise LicenseError('El código de licencia no tiene el formato esperado.')
            nonce = str(uuid4())
            data = {'device_id': self.record['device_id'], 'version': __version__,
                    'os': platform.system(), 'state': 'running', 'nonce': nonce}
            if code is not None:
                data.update(license_key=code, device_token=self.record['token'],
                            label='Equipo ' + self.record['device_id'][:4].upper())
            started = self.monotonic()
            try:
                result = request_json(self.url, '/v1/activate' if code is not None else '/v1/check-in',
                                      data, None if code is not None else self.record['token'])
                lease = self._verify(result['lease'], nonce)
                # La única autoridad de tiempo es iat, incluido en la firma.
                if (type(result['server_time']) is not int or result['server_time'] != lease.issued_at
                        or (self.lease and lease.issued_at < self.lease.issued_at)):
                    raise LicenseError('La respuesta del servicio no es válida.')
                with self.mutex:
                    # Ningún fallo de persistencia deja vivo el permiso anterior.
                    self.broken = True
                    self.anchor = None
                    # Registrar primero la respuesta firmada, antes de modificar keyring.
                    save_record({'lease': result['lease']}, self.directory / 'lease.json')
                    self.record['lease'] = result['lease']
                    self.record['revisions'][lease.license_id] = [lease.license_revision, lease.device_revision]
                    self.record['last_wall'] = self.wall()
                    self.record['trusted_now'] = lease.issued_at
                    self._persist()  # Denegaciones y revisiones se confirman antes de usarlas.
                    self.lease = lease
                    self.anchor = (lease.issued_at, started)
                    self.broken = False
                self.failures = 0
                self.next_attempt = self.monotonic() + 300 + random.uniform(0, 30)
                self.error = ''
            except (LicenseError, KeyError, TypeError, OSError) as exc:
                self.failures += 1
                delay = exc.seconds if isinstance(exc, RetryLater) else min(3600, 30 * 2 ** min(self.failures, 7))
                self.next_attempt = self.monotonic() + delay + random.uniform(0, 15)
                self.error = str(exc) if isinstance(exc, LicenseError) else 'No se pudo guardar o validar el permiso.'
                raise LicenseError(self.error) from None

    def start(self):
        if not self.required or self.worker is not None:
            return
        self.worker = threading.Thread(target=self._run, daemon=True, name='conxml-license')
        self.worker.start()

    def _run(self):
        while not self.stopped.is_set():
            if self.record["lease"] and self.monotonic() >= self.next_attempt:
                try:
                    self.sync()
                except LicenseError:
                    pass
            self.stopped.wait(1)

    def close(self):
        self.stopped.set()
        if self.worker and self.worker is not threading.current_thread():
            self.worker.join(timeout=1)
        # No se envía 'closed': un cierre tardío no debe ocultar otra sesión.
        # El servidor mostrará 'inactive' tras su umbral de última señal.
        if self.process_lock and (self.worker is None or not self.worker.is_alive()):
            self.process_lock.close()


_client = None
_client_lock = threading.Lock()


def get_client():
    global _client
    with _client_lock:
        if _client is None:
            _client = LicenseClient()
    return _client


def require_access():
    client = get_client()
    if client.required:
        # Permite renovar en CLI sin conceder nada ante un error de red.
        if client.monotonic() >= client.next_attempt:
            try:
                client.sync()
            except LicenseError:
                pass
        client.require()
