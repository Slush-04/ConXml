"""Actualizaciones voluntarias desde Releases públicos, nunca desde commits."""
from __future__ import annotations

import hashlib
import os
import platform
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from conxml import __version__

REPOSITORY = "Slush-04/ConXml"
LATEST_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_SIZE = 600 * 1024 * 1024


class UpdateError(RuntimeError):
    pass


def version_tuple(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", value):
        raise UpdateError("Versión inválida; se requiere X.Y.Z estable.")
    return tuple(int(n) for n in value.removeprefix("v").split("."))


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    sha256: str
    size: int
    name: str


class Updater:
    def __init__(self, cache: Path, *, current: str = __version__, session=None):
        self.cache = cache
        self.current = current
        self.session = session or requests.Session()
        # Solo código fuente permite el servidor de demostración; un .exe lo ignora.
        self.demo = os.environ.get("CONXML_UPDATE_DEMO_URL", "") if not getattr(sys, "frozen", False) else ""
        if self.demo and not self._local(self.demo):
            raise UpdateError("La demostración debe usar http://127.0.0.1:<puerto>/latest.")

    @staticmethod
    def _local(url):
        p = urlparse(url)
        return p.scheme == "http" and p.hostname == "127.0.0.1" and not p.username and not p.password

    def _safe_url(self, url, *, asset=False):
        if self.demo:
            if not self._local(url) or urlparse(url).netloc != urlparse(self.demo).netloc:
                raise UpdateError("URL ajena al servidor de pruebas.")
        else:
            p = urlparse(url)
            hosts = {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"} if asset else {"api.github.com"}
            if p.scheme != "https" or p.hostname not in hosts or p.username or p.password or p.port not in (None, 443):
                raise UpdateError("Origen de actualización no permitido.")

    def _get(self, url, *, asset=False, stream=False):
        # Validar cada redirect antes de conectar, evitando HTTP y otros orígenes.
        for _ in range(6):
            self._safe_url(url, asset=asset)
            response = self.session.get(url, timeout=(5, 20), stream=stream, allow_redirects=False,
                                        headers={"Accept": "application/octet-stream" if asset else "application/vnd.github+json"})
            if response.status_code in (301, 302, 303, 307, 308):
                from urllib.parse import urljoin
                url = urljoin(url, response.headers.get("Location", ""))
                response.close()
                continue
            return response
        raise UpdateError("Demasiadas redirecciones.")

    def check(self) -> Release | None:
        if not self.demo and (sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}):
            return None
        try:
            with self._get(self.demo or LATEST_URL) as response:
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                if len(response.content) > 1024 * 1024:
                    raise UpdateError("Respuesta de versiones demasiado grande.")
                data = response.json()
            if data.get("draft") or data.get("prerelease"):
                return None
            version = data["tag_name"].removeprefix("v")
            if version_tuple(version) <= version_tuple(self.current):
                return None
            name = f"ConXml-Setup-{version}-windows-x64.exe"
            for asset in data.get("assets", []):
                if asset.get("name") != name or asset.get("state") != "uploaded":
                    continue
                digest = asset.get("digest", "")
                if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                    continue
                size = asset.get("size")
                if type(size) is not int or not 0 < size <= MAX_SIZE:
                    continue
                url = asset["browser_download_url"]
                self._safe_url(url, asset=True)
                if not self.demo and url != f"https://github.com/{REPOSITORY}/releases/download/v{version}/{name}":
                    raise UpdateError("El instalador no pertenece a la versión publicada.")
                return Release(version, url, digest[7:], size, name)
            return None  # Una versión sin artefacto verificable no se anuncia.
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise UpdateError("No se pudo consultar la actualización. Puedes reintentar con conexión.") from exc

    def download(self, release: Release, progress=None) -> Path:
        self.cache.mkdir(parents=True, exist_ok=True)
        if release.name != f"ConXml-Setup-{release.version}-windows-x64.exe":
            raise UpdateError("Nombre de instalador inválido.")
        version_tuple(release.version)
        fd, temporary = tempfile.mkstemp(prefix=".descarga-", dir=self.cache)
        target = self.cache / release.name
        total = 0
        digest = hashlib.sha256()
        try:
            with os.fdopen(fd, "wb") as output, self._get(release.url, asset=True, stream=True) as response:
                response.raise_for_status()
                for block in response.iter_content(256 * 1024):
                    total += len(block)
                    if total > release.size or total > MAX_SIZE:
                        raise UpdateError("El instalador excede el tamaño publicado.")
                    output.write(block)
                    digest.update(block)
                    if progress:
                        progress(total, release.size)
            if total != release.size or digest.hexdigest() != release.sha256:
                raise UpdateError("Descarga incompleta o SHA-256 incorrecto. No se instalará.")
            os.replace(temporary, target)
            return target
        except requests.RequestException as exc:
            raise UpdateError("Falló la descarga. Puedes reintentar; tus datos están intactos.") from exc
        finally:
            Path(temporary).unlink(missing_ok=True)

    def launch(self, release: Release, path: Path):
        if self.demo or sys.platform != "win32" or not getattr(sys, "frozen", False):
            raise UpdateError("Instalación disponible solo en ConXml empaquetado para Windows.")
        if path.resolve() != (self.cache / release.name).resolve():
            raise UpdateError("Ruta del instalador inválida.")
        h = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                h.update(block)
        if path.stat().st_size != release.size or h.hexdigest() != release.sha256:
            raise UpdateError("El instalador cambió después de descargarlo.")
        # AppMutex impide sustituir la aplicación mientras este proceso sigue
        # vivo. Un proceso auxiliar espera a que ConXml termine y solo después
        # abre Setup; así el Run de Inno Setup no intenta lanzar la nueva app
        # mientras el mutex de la versión anterior aún existe.
        helper = self.cache / f".instalar-despues-{os.getpid()}.ps1"
        installer = str(path).replace("'", "''")
        helper.write_text(
            "$ErrorActionPreference = 'SilentlyContinue'\n"
            f"$installer = '{installer}'\n"
            f"try {{ Wait-Process -Id {os.getpid()} -ErrorAction Stop }} catch {{ }}\n"
            "Start-Process -FilePath $installer -Wait\n"
            "Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue\n"
            "Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue\n",
            encoding="utf-8",
        )
        detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.Popen(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
             "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass",
             "-File", str(helper)],
            close_fds=True,
            creationflags=detached | no_window,
        )
