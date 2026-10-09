"""Actualizaciones voluntarias desde Releases públicos, nunca desde commits.

Soporta actualización directa mediante paquete ZIP (conxml.exe y conxml-cli.exe)
con validación SHA-256, reemplazo seguro mediante helper desacoplado, rollback
automático en caso de fallo, y preservación total de datos del usuario.
Conserva el instalador interactivo como método de instalación inicial y rescate.
"""
from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from urllib.parse import urlparse

import requests
from conxml import __version__
from conxml.config import Config

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
    kind: str = "zip"  # "zip" para reemplazo directo o "installer" para setup interactivo


def generar_script_actualizador(
    script_path: Path,
    *,
    parent_pid: int,
    target_dir: Path,
    staging_dir: Path,
    backup_dir: Path,
    log_file: Path,
    expected_version: str = "",
) -> Path:
    """Genera el script PowerShell que reemplaza los binarios tras el cierre de ConXml."""
    contenido = f"""# Script de actualización desatendida para ConXml
param(
    [Parameter(Mandatory=$false)][int]$ParentPid = {parent_pid},
    [Parameter(Mandatory=$false)][string]$TargetDir = '{str(target_dir).replace("'", "''")}',
    [Parameter(Mandatory=$false)][string]$StagingDir = '{str(staging_dir).replace("'", "''")}',
    [Parameter(Mandatory=$false)][string]$BackupDir = '{str(backup_dir).replace("'", "''")}',
    [Parameter(Mandatory=$false)][string]$LogFile = '{str(log_file).replace("'", "''")}',
    [Parameter(Mandatory=$false)][string]$ExpectedVersion = '{expected_version}'
)
$ErrorActionPreference = "Stop"

function Write-Log($msg) {{
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $line = "$timestamp [ACTUALIZADOR] $msg"
    Write-Output $line
    if ($LogFile) {{
        try {{
            $dir = Split-Path -Parent $LogFile
            if (-not (Test-Path $dir)) {{ New-Item -ItemType Directory -Path $dir -Force | Out-Null }}
            Add-Content -Path $LogFile -Value $line -Encoding utf8
        }} catch {{}}
    }}
}}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$form = New-Object System.Windows.Forms.Form
$form.Text = "Actualizando ConXml"
$form.Width = 470
$form.Height = 150
$form.StartPosition = "CenterScreen"
$form.TopMost = $true
$form.ControlBox = $false
$label = New-Object System.Windows.Forms.Label
$label.Left = 18
$label.Top = 18
$label.Width = 420
$label.Height = 38
$label.Text = "Preparando actualización..."
$bar = New-Object System.Windows.Forms.ProgressBar
$bar.Left = 18
$bar.Top = 66
$bar.Width = 420
$bar.Height = 22
$bar.Style = "Marquee"
$bar.MarqueeAnimationSpeed = 24
$form.Controls.Add($label)
$form.Controls.Add($bar)
$form.Show()
[System.Windows.Forms.Application]::DoEvents()

function Set-UpdateStatus($message, $percent = -1) {{
    $label.Text = $message
    if ($percent -ge 0) {{
        $bar.Style = "Continuous"
        $bar.MarqueeAnimationSpeed = 0
        $bar.Value = [Math]::Max(0, [Math]::Min(100, $percent))
    }} else {{
        $bar.Style = "Marquee"
        $bar.MarqueeAnimationSpeed = 24
    }}
    $form.Refresh()
    [System.Windows.Forms.Application]::DoEvents()
    Write-Log $message
}}

function Show-UpdateFailure($message) {{
    Write-Log "ERROR: $message"
    [System.Windows.Forms.MessageBox]::Show("$message`n`nRevisa el diagnóstico en:`n$LogFile", "No se pudo actualizar ConXml", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
    $form.Close()
}}

Write-Log "Iniciando actualización de ConXml $ExpectedVersion para PID $ParentPid hacia $TargetDir"
Set-UpdateStatus "Cerrando ConXml para instalar la actualización..."

# 1. Esperar a que el proceso padre termine
if ($ParentPid -gt 0) {{
    $waited = 0
    $timeout = 30
    while ($waited -lt $timeout) {{
        $p = Get-Process -Id $ParentPid -ErrorAction SilentlyContinue
        if (-not $p) {{
            Write-Log "Proceso padre $ParentPid finalizado tras $waited s."
            break
        }}
        Start-Sleep -Milliseconds 500
        $waited += 0.5
    }}
    if (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) {{
        Show-UpdateFailure "ConXml no se cerró a tiempo. No se cambiaron los archivos."
        exit 1
    }}
}}

Start-Sleep -Milliseconds 600

# 2. Respaldar binarios existentes
Set-UpdateStatus "Guardando respaldo de la versión anterior..." 15
if (-not (Test-Path $BackupDir)) {{
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}}

$archivos = @("conxml.exe", "conxml-cli.exe")
$faltante = $false
foreach ($f in $archivos) {{
    $origen = Join-Path $StagingDir $f
    if (-not (Test-Path -LiteralPath $origen -PathType Leaf) -or (Get-Item -LiteralPath $origen).Length -le 0) {{
        Write-Log "ERROR: El paquete no contiene un $f válido."
        $faltante = $true
    }}
}}
if ($faltante) {{
    Write-Log "No se modificó la instalación porque el paquete está incompleto."
    exit 1
}}

foreach ($f in $archivos) {{
    $actual = Join-Path $TargetDir $f
    if (Test-Path $actual) {{
        try {{
            Copy-Item -Path $actual -Destination (Join-Path $BackupDir $f) -Force
            Write-Log "Respaldado $f en $BackupDir"
        }} catch {{
            Write-Log "ADVERTENCIA: no se pudo respaldar ${{f}}: ${{_}}"
        }}
    }}
}}

# 3. Reemplazar binarios desde staging
Set-UpdateStatus "Instalando ConXml $ExpectedVersion..." 45
$fallo = $false
$indiceArchivo = 0
foreach ($f in $archivos) {{
    $origen = Join-Path $StagingDir $f
    if (Test-Path $origen) {{
        $destino = Join-Path $TargetDir $f
        try {{
            Set-UpdateStatus "Instalando $f..." (45 + ($indiceArchivo * 25))
            Copy-Item -Path $origen -Destination $destino -Force
            $hashOrigen = (Get-FileHash -LiteralPath $origen -Algorithm SHA256).Hash
            $hashDestino = (Get-FileHash -LiteralPath $destino -Algorithm SHA256).Hash
            if ($hashOrigen -ne $hashDestino) {{
                throw "La copia de $f no coincide con el archivo descargado."
            }}
            Write-Log "Verificado $f (SHA-256 $hashDestino) en $destino"
        }} catch {{
            Write-Log "ERROR al copiar ${{f}}: ${{_}}"
            $fallo = $true
            break
        }}
    }}
    $indiceArchivo += 1
}}

# El CLI comparte el mismo paquete Python que la interfaz y permite comprobar
# la versión embebida antes de relanzar ConXml.
if (-not $fallo) {{
    try {{
        $cliExe = Join-Path $TargetDir "conxml-cli.exe"
        $versionInstalada = (& $cliExe --version | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or $versionInstalada -ne "conxml $ExpectedVersion") {{
            throw "Se esperaba conxml $ExpectedVersion y el ejecutable instalado reportó '$versionInstalada'."
        }}
        Write-Log "Versión comprobada antes del arranque: $versionInstalada"
    }} catch {{
        Write-Log "ERROR al comprobar la versión instalada: $($_.Exception.Message)"
        $fallo = $true
    }}
}}

# 4. Rollback en caso de fallo al copiar
if ($fallo) {{
    Write-Log "Fallo en reemplazo. Restaurando respaldo (rollback)..."
    foreach ($f in $archivos) {{
        $bak = Join-Path $BackupDir $f
        if (Test-Path $bak) {{
            try {{
                Copy-Item -Path $bak -Destination (Join-Path $TargetDir $f) -Force
                Write-Log "Restaurado $f desde respaldo."
            }} catch {{
                Write-Log "ERROR crítico al restaurar ${{f}}: ${{_}}"
            }}
        }}
    }}
    $exeRestaurado = Join-Path $TargetDir "conxml.exe"
    if (Test-Path $exeRestaurado) {{
        Start-Process -FilePath $exeRestaurado
        Write-Log "Relanzada versión anterior tras rollback."
    }}
    Show-UpdateFailure "No se pudieron reemplazar los archivos. Se restauró la versión anterior."
    exit 1
}}

# 5. Relanzar el ejecutable actualizado
$nuevoExe = Join-Path $TargetDir "conxml.exe"
if (Test-Path $nuevoExe) {{
    Set-UpdateStatus "Iniciando ConXml $ExpectedVersion para comprobar la actualización..." 85
    $nuevoProc = Start-Process -FilePath $nuevoExe -PassThru
    $ventanaAbierta = $false
    for ($i = 0; $i -lt 40; $i++) {{
        Start-Sleep -Milliseconds 500
        try {{
            $nuevoProc.Refresh()
            if ($nuevoProc.HasExited) {{ break }}
            if ($nuevoProc.MainWindowHandle -ne [IntPtr]::Zero) {{ $ventanaAbierta = $true; break }}
        }} catch {{}}
        [System.Windows.Forms.Application]::DoEvents()
    }}
    if (-not $ventanaAbierta) {{
        if (-not $nuevoProc.HasExited) {{ Stop-Process -Id $nuevoProc.Id -Force -ErrorAction SilentlyContinue }}
        Write-Log "ERROR: ConXml $ExpectedVersion no abrió una ventana. Ejecutando rollback."
        foreach ($f in $archivos) {{
            $bak = Join-Path $BackupDir $f
            if (Test-Path $bak) {{
                Copy-Item -Path $bak -Destination (Join-Path $TargetDir $f) -Force
            }}
        }}
        Start-Process -FilePath $nuevoExe
        Show-UpdateFailure "ConXml $ExpectedVersion no pudo abrir su ventana. Se restauró la versión anterior."
        exit 1
    }}
}} else {{
    Show-UpdateFailure "No se encontró el ejecutable de ConXml después de instalar."
    exit 1
}}

# 6. Limpieza de staging
try {{
    Remove-Item -Path $StagingDir -Recurse -Force -ErrorAction SilentlyContinue
}} catch {{}}

Set-UpdateStatus "ConXml $ExpectedVersion se abrió correctamente. Actualización completada." 100
Write-Log "Actualización completada exitosamente."
[System.Windows.Forms.MessageBox]::Show("ConXml se actualizó a la versión $ExpectedVersion y se abrió correctamente.", "Actualización completada", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
$form.Close()
"""
    script_path.parent.mkdir(parents=True, exist_ok=True)
    # Windows PowerShell 5.1 interpreta archivos UTF-8 sin BOM como ANSI.
    # El BOM conserva correctamente acentos en mensajes y rutas del script.
    script_path.write_text(contenido, encoding="utf-8-sig")
    return script_path


def _extraer_paquete_seguro(archivo: zipfile.ZipFile, destino: Path) -> None:
    """Extrae solo los dos binarios esperados, sin rutas arbitrarias."""
    permitidos = {"conxml.exe", "conxml-cli.exe"}
    encontrados: set[str] = set()
    total_descomprimido = 0
    destino_resuelto = destino.resolve()

    for info in archivo.infolist():
        ruta = PurePosixPath(info.filename)
        if info.is_dir():
            continue
        if ruta.is_absolute() or len(ruta.parts) != 1 or ruta.name not in permitidos:
            raise UpdateError("El paquete contiene una ruta o archivo no permitido.")
        # El bit de enlace simbólico en ZIP no debe poder escapar del staging.
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise UpdateError("El paquete no puede contener enlaces simbólicos.")
        if info.file_size < 0 or info.file_size > MAX_SIZE:
            raise UpdateError("Un binario del paquete excede el tamaño permitido.")
        total_descomprimido += info.file_size
        if total_descomprimido > MAX_SIZE:
            raise UpdateError("El contenido descomprimido excede el tamaño permitido.")
        objetivo = (destino / ruta.name).resolve()
        if destino_resuelto not in objetivo.parents:
            raise UpdateError("Ruta de extracción fuera del directorio temporal.")
        with archivo.open(info, "r") as origen, objetivo.open("wb") as salida:
            shutil.copyfileobj(origen, salida, length=1024 * 1024)
        encontrados.add(ruta.name)

    if "conxml.exe" not in encontrados:
        raise UpdateError("El paquete descargado no contiene conxml.exe.")


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

            zip_name = f"ConXml-{version}-windows-x64.zip"
            installer_name = f"ConXml-Setup-{version}-windows-x64.exe"

            assets_by_name = {
                a.get("name"): a for a in data.get("assets", []) if a.get("state") == "uploaded"
            }

            # Prioridad 1: Paquete ZIP para actualización directa sin instalador
            # Prioridad 2: Instalador Setup (para compatibilidad hacia atrás)
            candidatos = []
            if zip_name in assets_by_name:
                candidatos.append((zip_name, "zip"))
            if installer_name in assets_by_name:
                candidatos.append((installer_name, "installer"))

            for name, kind in candidatos:
                asset = assets_by_name[name]
                digest = asset.get("digest", "")
                if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                    continue
                size = asset.get("size")
                if type(size) is not int or not 0 < size <= MAX_SIZE:
                    continue
                url = asset["browser_download_url"]
                self._safe_url(url, asset=True)
                if not self.demo and url != f"https://github.com/{REPOSITORY}/releases/download/v{version}/{name}":
                    raise UpdateError("El artefacto no pertenece a la versión publicada.")
                return Release(version, url, digest[7:], size, name, kind=kind)

            return None
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise UpdateError("No se pudo consultar la actualización. Puedes reintentar con conexión.") from exc

    def download(self, release: Release, progress=None) -> Path:
        self.cache.mkdir(parents=True, exist_ok=True)
        valid_names = (
            f"ConXml-{release.version}-windows-x64.zip",
            f"ConXml-Setup-{release.version}-windows-x64.exe",
        )
        if release.name not in valid_names:
            raise UpdateError("Nombre de archivo de actualización inválido.")
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
                        raise UpdateError("El archivo excede el tamaño publicado.")
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

    def apply_update(
        self,
        release: Release,
        path: Path,
        *,
        target_dir: Path | None = None,
        parent_pid: int | None = None,
    ) -> Path:
        """Extrae el paquete de actualización, valida los binarios y lanza el helper de sustitución."""
        if path.resolve() != (self.cache / release.name).resolve():
            raise UpdateError("Ruta del archivo de actualización inválida.")

        h = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                h.update(block)
        if path.stat().st_size != release.size or h.hexdigest() != release.sha256:
            raise UpdateError("El archivo de actualización cambió después de descargarlo.")

        if release.kind == "installer" or path.name.endswith(".exe"):
            self.launch(release, path)
            return path

        staging_dir = self.cache / "staging" / release.version
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(path, "r") as z:
                _extraer_paquete_seguro(z, staging_dir)
        except UpdateError:
            raise
        except (zipfile.BadZipFile, OSError) as exc:
            raise UpdateError(f"Archivo de actualización no es un ZIP válido: {exc}") from exc

        exe_staging = staging_dir / "conxml.exe"
        if not exe_staging.is_file() or exe_staging.stat().st_size == 0:
            raise UpdateError("El paquete descargado no contiene conxml.exe.")

        if target_dir is None:
            if getattr(sys, "frozen", False):
                target_dir = Path(sys.executable).resolve().parent
            else:
                target_dir = self.cache / "installed"
                target_dir.mkdir(parents=True, exist_ok=True)

        backup_dir = self.cache / "backup"
        log_file = Config().logs_dir / "actualizacion.log"
        script_path = self.cache / "actualizar.ps1"

        generar_script_actualizador(
            script_path,
            parent_pid=parent_pid or os.getpid(),
            target_dir=target_dir,
            staging_dir=staging_dir,
            backup_dir=backup_dir,
            log_file=log_file,
            expected_version=release.version,
        )

        if sys.platform == "win32" and not self.demo and getattr(sys, "frozen", False):
            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden",
                "-File", str(script_path),
            ]
            flags = 0
            if hasattr(subprocess, "DETACHED_PROCESS"):
                flags |= subprocess.DETACHED_PROCESS
            if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                flags |= subprocess.CREATE_NEW_PROCESS_GROUP
            subprocess.Popen(cmd, creationflags=flags, close_fds=True)

        return script_path

    def launch(self, release: Release, path: Path):
        """Lanza el instalador interactivo como método alternativo o de rescate."""
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
