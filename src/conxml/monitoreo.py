"""Presencia opcional de la aplicación. Solo envía versión, SO y estado del proceso."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import platform
import queue
import tempfile
import threading
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import keyring
import requests

from conxml import __version__
from conxml.config import Config

SERVICE = "ConXml-Monitor"
INTERVAL = 30


class MonitoringError(Exception):
    pass


def config_path() -> Path:
    # Fuera de los datos fiscales, respaldos y carpetas que se pueden copiar a otro equipo.
    return Config().ubicacion_path.with_name("monitoreo.json")


def validate_url(value) -> str:
    try:
        if not isinstance(value, str):
            raise ValueError()
        parts = urlsplit(value.strip())
        local = parts.hostname in ("localhost", "127.0.0.1", "::1")
        if (not parts.hostname or parts.username is not None or parts.password is not None
                or parts.query or parts.fragment or parts.path not in ("", "/")
                or (parts.scheme != "https" and not (parts.scheme == "http" and local))):
            raise ValueError()
        parts.port
        return f"{parts.scheme}://{parts.netloc}"
    except ValueError:
        raise MonitoringError("La configuración debe indicar un servicio HTTPS válido.") from None


def validate_record(record: dict) -> dict:
    try:
        if not isinstance(record, dict) or type(record.get("schema")) is not int or record["schema"] != 1:
            raise ValueError()
        identifier = record["device_id"]
        if not isinstance(identifier, str) or str(UUID(identifier)) != identifier:
            raise ValueError()
        alias = record["alias"]
        if not isinstance(alias, str) or not alias.strip() or len(alias) > 80 or any(ord(c) < 32 for c in alias):
            raise ValueError()
        return {"schema": 1, "service_url": validate_url(record["service_url"]),
                "device_id": identifier, "alias": alias, "enabled": record.get("enabled") is True}
    except (KeyError, TypeError, ValueError, AttributeError):
        raise MonitoringError("El archivo de monitoreo no es válido.") from None


def read_record(path: Path) -> dict:
    try:
        with path.open("rb") as source:
            raw = source.read(4097)
        if len(raw) > 4096:
            raise ValueError()
        return json.loads(raw)
    except (OSError, ValueError, UnicodeError):
        raise MonitoringError("No se pudo leer la configuración de monitoreo.") from None


def save_record(record: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            os.chmod(temporary, 0o600)
            json.dump(record, output, ensure_ascii=True)
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def import_configuration(source: Path, destination: Path | None = None) -> dict:
    record = read_record(source)
    clean = validate_record(record)
    token = record.get("device_token")
    if not isinstance(token, str) or not 32 <= len(token) <= 256 or not token.isascii() or any(c.isspace() for c in token):
        raise MonitoringError("El archivo no contiene una credencial de equipo válida.")
    clean["enabled"] = True
    previous = None
    changed = False
    try:
        previous = keyring.get_password(SERVICE, clean["device_id"])
        keyring.set_password(SERVICE, clean["device_id"], token)
        changed = True
        save_record(clean, destination or config_path())
    except Exception:
        if changed:
            try:
                if previous:
                    keyring.set_password(SERVICE, clean["device_id"], previous)
                else:
                    keyring.delete_password(SERVICE, clean["device_id"])
            except Exception:
                pass
        raise MonitoringError("No se pudo guardar la configuración y su credencial en el almacén seguro del sistema.") from None
    return clean


def set_enabled(enabled: bool) -> None:
    record = validate_record(read_record(config_path()))
    record["enabled"] = bool(enabled)
    try:
        save_record(record, config_path())
    except OSError:
        raise MonitoringError("No se pudo guardar la preferencia de monitoreo.") from None


@dataclass(frozen=True)
class ReporterConfig:
    url: str
    device_id: str
    token: str = field(repr=False)


def control_path() -> Path:
    return config_path().with_name("monitoreo-control.json")


class ControlState:
    """Última política recibida y confirmaciones pendientes, persistidas sin credenciales."""
    def __init__(self, identity: dict, path: Path | None = None, *, recover=False):
        self.identity = {key: identity[key] for key in ("device_id", "service_url")}
        self.path = path or control_path()
        self.lock = threading.RLock()
        self.active = True
        self.revision = -1
        self.applied_revision = 0
        self.blocked = False
        self.seen = []
        self.pending_acks = []
        if recover:
            self.blocked = True
            return
        try:
            with self.path.open("rb") as source:
                raw = source.read(131073)
            record = json.loads(raw) if len(raw) <= 131072 else {}
            if not isinstance(record, dict):
                raise ValueError()
            if record.get("identity") == self.identity:
                if (type(record.get("revision")) is not int or not 0 <= record["revision"] <= 2**53
                        or type(record.get("blocked")) is not bool):
                    raise ValueError()
                seen, pending = record.get("seen", []), record.get("pending_acks", [])
                if not isinstance(seen, list) or not isinstance(pending, list) or len(seen) > 1024 or len(pending) > 100:
                    raise ValueError()
                for identifier in seen + pending:
                    if not isinstance(identifier, str) or str(UUID(identifier)) != identifier:
                        raise ValueError()
                applied = record.get("applied_revision", 0)
                if type(applied) is not int or not 0 <= applied <= record["revision"]:
                    raise ValueError()
                self.revision, self.blocked, self.applied_revision = record["revision"], record["blocked"], applied
                self.seen, self.pending_acks = seen, pending
        except FileNotFoundError:
            pass
        except (OSError, ValueError, UnicodeError, TypeError):
            # No cambiar un bloqueo válido durante la sesión por un error de lectura.
            raise MonitoringError("No se pudo leer el estado de acceso guardado. Contacta al administrador para recuperar la configuración.") from None

    def _save(self, **updates):
        if not self.active:
            raise MonitoringError("La configuración de administración cambió.")
        record = {"identity": self.identity, "revision": self.revision, "applied_revision": self.applied_revision,
                  "blocked": self.blocked, "seen": self.seen, "pending_acks": self.pending_acks, **updates}
        save_record(record, self.path)
        for key, value in updates.items():
            setattr(self, key, value)

    def deactivate(self):
        with self.lock:
            self.active = False

    def apply_policy(self, policy):
        with self.lock:
            if policy["revision"] < self.revision:
                return
            if policy["revision"] == self.revision:
                return
            self._save(revision=policy["revision"], blocked=policy["blocked"])

    def acknowledge_policy(self):
        with self.lock:
            if self.revision >= 0 and self.applied_revision != self.revision:
                self._save(applied_revision=self.revision)

    def acknowledge_messages(self, identifiers):
        with self.lock:
            seen = list(dict.fromkeys(self.seen + identifiers))[-1024:]
            pending = list(dict.fromkeys(self.pending_acks + identifiers))
            if len(pending) > 100:
                raise MonitoringError("Hay demasiadas confirmaciones pendientes. Conecta con el servidor antes de continuar.")
            self._save(seen=seen, pending_acks=pending)

    def confirm_sent(self, identifiers):
        with self.lock:
            pending = [value for value in self.pending_acks if value not in identifiers]
            if pending != self.pending_acks:
                self._save(pending_acks=pending)

    def acknowledgements(self):
        with self.lock:
            return {"protocol": 2, "control_ack": self.applied_revision, "message_acks": self.pending_acks[:20]}


def parse_control_response(response) -> dict:
    raw = bytearray()
    for chunk in response.iter_content(16384):
        raw.extend(chunk)
        if len(raw) > 262144:
            raise ValueError()
    result = json.loads(raw)
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise ValueError()
    if "control" not in result and "messages" not in result:
        return result  # Compatibilidad con un servidor de presencia anterior.
    policy, messages = result["control"], result["messages"]
    if (not isinstance(policy, dict) or type(policy.get("revision")) is not int
            or not 0 <= policy["revision"] <= 2**53 or type(policy.get("blocked")) is not bool
            or not isinstance(messages, list) or len(messages) > 20):
        raise ValueError()
    for message in messages:
        if (not isinstance(message, dict) or not isinstance(message.get("id"), str)
                or str(UUID(message["id"])) != message["id"] or not isinstance(message.get("text"), str)
                or not message["text"].strip() or len(message["text"]) > 2000):
            raise ValueError()
    return result


class PresenceReporter:
    def __init__(self, config: ReporterConfig, *, interval=INTERVAL, control_state=None, on_control=None):
        self.config = config
        self.interval = interval
        self.session_id = str(uuid4())
        self.sequence = 0
        self.control_state = control_state
        self.on_control = on_control
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="conxml-presence")

    def start(self):
        self.thread.start()

    def _send(self, state: str) -> bool:
        self.sequence += 1
        payload = {"session_id": self.session_id, "sequence": self.sequence, "version": __version__,
                   "os": f"{platform.system()} {platform.release()}"[:100], "state": state}
        if self.control_state is not None:
            payload.update(self.control_state.acknowledgements())
        try:
            with requests.post(self.config.url + f"/v1/devices/{self.config.device_id}/heartbeat",
                               json=payload, headers={"Authorization": f"Bearer {self.config.token}"},
                               timeout=(2, 3), allow_redirects=False, stream=True) as response:
                if response.status_code == 401:
                    self.stopped.set()  # Revocado: no insistir hasta cambiar la configuración.
                if response.status_code != 200:
                    return False
                if self.control_state is not None and state == "running" and not self.stopped.is_set():
                    result = parse_control_response(response)
                    self.control_state.confirm_sent(payload["message_acks"])
                    if "control" in result and self.on_control:
                        self.on_control(result)
                return True
        except (requests.RequestException, ValueError, KeyError, TypeError, OSError, MonitoringError):
            return False  # El monitoreo nunca interrumpe el trabajo local.

    def _run(self):
        try:
            while not self.stopped.is_set():
                self._send("running")
                if self.stopped.wait(self.interval):
                    break
        finally:
            self._send("closed")

    def stop(self, *, wait=0):
        self.stopped.set()
        if wait and self.thread.ident is not None:
            self.thread.join(timeout=wait)


class MonitoringController:
    def __init__(self, root=None):
        self.root = root
        self.reporter = None
        self.control_state = None
        self.view = None
        self._events = queue.Queue()
        self._closed = False
        self.reload()
        if root is not None:
            from conxml.ui.control_remoto import RemoteControlView
            self.view = RemoteControlView(root, self._acknowledge_messages)
            root.after(100, self._poll)

    def reload(self):
        if self.reporter:
            self.reporter.stop()
            self.reporter = None
        try:
            path = config_path()
            if not path.exists():
                return
            record = validate_record(read_record(path))
            identity = {key: record[key] for key in ("device_id", "service_url")}
            if self.control_state and self.control_state.identity == identity:
                state = self.control_state
            else:
                if self.control_state:
                    self.control_state.deactivate()
                    if self.view:
                        self.view.clear_messages()
                try:
                    state = ControlState(record)
                except MonitoringError:
                    state = ControlState(record, recover=True)
            self.control_state = state
            if not record["enabled"]:
                return
            token = keyring.get_password(SERVICE, record["device_id"])
            if not token or not 32 <= len(token) <= 256 or not token.isascii() or any(c.isspace() for c in token):
                return
            state = self.control_state
            self.reporter = PresenceReporter(ReporterConfig(record["service_url"], record["device_id"], token),
                control_state=state, on_control=lambda result: self._events.put((state, result)))
            self.reporter.start()
        except Exception:
            # No registrar credenciales ni el contenido del archivo importado.
            self.reporter = None

    def _acknowledge_messages(self, identifiers):
        if self.control_state:
            self.control_state.acknowledge_messages(identifiers)

    def _poll(self):
        if self._closed:
            return
        try:
            while True:
                state, result = self._events.get_nowait()
                if state is not self.control_state:
                    continue
                state.apply_policy(result["control"])
                self.view.queue_messages([message for message in result["messages"] if message["id"] not in state.seen])
        except queue.Empty:
            pass
        except (OSError, MonitoringError):
            # Sin persistencia no se confirma una instrucción como aplicada.
            pass
        try:
            if self.control_state and self.view.sync(self.control_state.blocked):
                self.control_state.acknowledge_policy()
        except (OSError, MonitoringError):
            pass
        self.root.after(250, self._poll)

    def close(self, *, wait=0):
        self._closed = True
        if self.control_state:
            self.control_state.deactivate()
        if self.reporter:
            self.reporter.stop(wait=wait)
            self.reporter = None
