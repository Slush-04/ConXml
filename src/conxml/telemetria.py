"""Historial técnico acotado. Nunca guarda mensajes, rutas ni datos fiscales."""
from __future__ import annotations

from functools import wraps
import json
import threading
import time
from uuid import UUID, uuid4

from conxml.monitoreo import save_record

CODES = frozenset(('operation_failed', 'result_failed', 'ui_callback_failed', 'startup_failed',
                   'command_failed', 'update_check_failed', 'update_download_failed', 'update_install_failed'))
TYPES = frozenset(('Error', 'ValueError', 'TypeError', 'OSError', 'RuntimeError', 'TimeoutError',
                   'ConnectionError', 'PermissionError', 'FileNotFoundError', 'UpdateError', 'TclError'))
LIMIT_SECONDS = 30 * 86400
_journal = None


def report_error(code, exc=None):
    if _journal is not None and code in CODES:
        _journal.error(code, exc)


def technical_diagnostic(code):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                report_error(code, exc)
                raise
        return wrapped
    return decorate


class Journal:
    """Outbox local independiente del permiso; una falla del historial no bloquea uso."""
    def __init__(self, directory, device_id, *, wall=time.time, monotonic=time.monotonic, kind='cli'):
        self.path = directory / 'telemetry.json'
        self.device_id, self.wall, self.monotonic = device_id, wall, monotonic
        self.lock = threading.RLock()
        self.origin = monotonic()
        self.sessions, self.diagnostics = [], []
        self.update_stamps = {}
        try:
            with self.path.open('rb') as stream:
                raw = stream.read(65537)
            data = json.loads(raw) if len(raw) <= 65536 else {}
            if data.get('device_id') == device_id:
                stamps = data.get('update_stamps', {})
                if isinstance(stamps, dict):
                    self.update_stamps = {k: v for k, v in stamps.items() if k in ('actualizacion.log', 'actualizacion-setup.log') and isinstance(v, str) and len(v) < 100}
                for session in data.get('sessions', [])[-30:]:
                    # Construir de nuevo impide retransmitir campos ajenos al contrato.
                    identifier = str(UUID(session['id']))
                    integers = [session[k] for k in ('sequence', 'started_at', 'observed_at', 'elapsed_seconds')]
                    if any(type(v) is not int or not 0 <= v <= 2**53 - 1 for v in integers):
                        continue
                    if session['state'] not in ('running', 'closed', 'interrupted') or session['kind'] not in ('gui', 'cli', 'scheduled'):
                        continue
                    start = session['started_at']
                    state = 'interrupted' if session['state'] == 'running' else session['state']
                    self.sessions.append(dict(id=identifier, sequence=session['sequence'] + 1,
                        started_at=start, observed_at=max(start, session['observed_at']),
                        ended_at=max(start, session['observed_at']), elapsed_seconds=min(LIMIT_SECONDS, session['elapsed_seconds']),
                        state=state, kind=session['kind']))
                for event in data.get('diagnostics', [])[-50:]:
                    if event.get('code') in CODES and event.get('exception_type') in TYPES:
                        self.diagnostics.append(dict(id=str(UUID(event['id'])), code=event['code'], exception_type=event['exception_type']))
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            self.sessions, self.diagnostics = [], []
        now = max(0, int(wall()))
        self.current = dict(id=str(uuid4()), sequence=0, started_at=now, observed_at=now,
                            ended_at=None, elapsed_seconds=0, state='running', kind=kind)
        self.sessions = self.sessions[-29:] + [self.current]
        self._save()

    def _save(self):
        try:
            save_record(dict(schema=1, device_id=self.device_id, sessions=self.sessions, diagnostics=self.diagnostics, update_stamps=self.update_stamps), self.path)
        except (OSError, ValueError, TypeError):
            pass

    def observe(self, closed=False):
        elapsed = min(LIMIT_SECONDS, max(0, int(self.monotonic() - self.origin)))
        self.current.update(elapsed_seconds=elapsed, observed_at=self.current['started_at'] + elapsed)
        self.current['sequence'] += 1
        if closed:
            self.current.update(state='closed', ended_at=self.current['observed_at'])

    def payload(self, closed=False):
        with self.lock:
            self.observe(closed)
            selected = [s for s in self.sessions if s is not self.current][:4] + [self.current]
            self._save()
            return dict(schema=1, current_session_id=self.current['id'],
                        sessions=[{k: v for k, v in s.items() if k != 'observed_at'} for s in selected],
                        diagnostics=[dict(e) for e in self.diagnostics[:5]])

    def acknowledge(self, ack, sent):
        # Solo confirmar identificadores efectivamente enviados y su revisión exacta.
        if (not isinstance(ack, dict) or not isinstance(ack.get('sessions'), list)
                or not isinstance(ack.get('diagnostics'), list)):
            return
        with self.lock:
            pairs = {(s['id'], s['sequence']) for s in sent['sessions']}
            confirmed = {(s.get('id'), s.get('sequence')) for s in ack.get('sessions', []) if isinstance(s, dict) and isinstance(s.get('id'), str) and type(s.get('sequence')) is int} & pairs
            self.sessions = [s for s in self.sessions if (s is self.current and s['state'] == 'running') or (s['id'], s['sequence']) not in confirmed]
            ids = {e['id'] for e in sent['diagnostics']} & {v for v in ack.get('diagnostics', []) if isinstance(v, str)}
            self.diagnostics = [e for e in self.diagnostics if e['id'] not in ids]
            self._save()

    def error(self, code, exc):
        with self.lock:
            # Clasificar únicamente por nombre permitido; jamás str(exc) o traceback.
            name = type(exc).__name__
            self.diagnostics = (self.diagnostics + [dict(id=str(uuid4()), code=code,
                                exception_type=name if name in TYPES else 'Error')])[-50:]
            self._save()

    def capture_update_result(self, logs_dir):
        # Reconocer únicamente marcadores del helper; nunca enviar el log ni su texto.
        for name in ('actualizacion.log', 'actualizacion-setup.log'):
            try:
                path = logs_dir / name
                stat = path.stat()
                stamp = f'{stat.st_mtime_ns}:{stat.st_size}'
                if self.update_stamps.get(name) == stamp:
                    continue
                with path.open('rb') as stream:
                    stream.seek(max(0, stat.st_size - 65536))
                    text = stream.read(65536).decode('utf-8', errors='replace')
                failed = max(text.rfind('ERROR de actualización:'), text.rfind('ERROR crítico durante rollback:'),
                             text.rfind('ERROR no controlado:'), text.rfind('ERROR:'))
                success = text.rfind('Actualización completada exitosamente.')
                if failed >= 0 and failed > success:
                    self.error('update_install_failed', None)
                if max(failed, success) >= 0:
                    self.update_stamps[name] = stamp
                    self._save()
            except OSError:
                pass

    def close(self):
        with self.lock:
            if self.current['state'] == 'running':
                self.observe(closed=True)
                self._save()
