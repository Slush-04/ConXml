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
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from urllib.parse import urlparse

import requests
from conxml import __version__
from conxml.config import Config
from conxml.windows_process import launch_powershell

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


# Esperar también al bootloader onefile y al CLI; el PID de la GUI no basta.
WAIT_INSTALLED_PROCESSES = r"""
function Wait-InstalledProcesses {
    $executables = @((Join-Path $TargetDir "conxml.exe"), (Join-Path $TargetDir "conxml-cli.exe"))
    $deadline = (Get-Date).AddSeconds(60)
    do {
        $active = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
            $_.ExecutablePath -and $executables -contains $_.ExecutablePath
        })
        if ($active.Count -eq 0) { return }
        if ((Get-Date) -ge $deadline) {
            throw "ConXml sigue en uso (PID $($active.ProcessId -join ', ')). Cierra sus otras instancias y reintenta."
        }
        Start-Sleep -Milliseconds 500
    } while ($true)
}
"""


def generar_script_actualizador(
    script_path: Path,
    *,
    parent_pid: int,
    target_dir: Path,
    staging_dir: Path,
    backup_dir: Path,
    log_file: Path,
    expected_version: str = "",
    ready_file: Path | None = None,
    show_completion: bool = True,
) -> Path:
    """Genera el script PowerShell que reemplaza los binarios tras el cierre de ConXml."""
    contenido = f"""# Script de actualización desatendida para ConXml
param(
    [Parameter(Mandatory=$false)][int]$ParentPid = {parent_pid},
    [Parameter(Mandatory=$false)][string]$TargetDir = '{str(target_dir).replace("'", "''")}',
    [Parameter(Mandatory=$false)][string]$StagingDir = '{str(staging_dir).replace("'", "''")}',
    [Parameter(Mandatory=$false)][string]$BackupDir = '{str(backup_dir).replace("'", "''")}',
    [Parameter(Mandatory=$false)][string]$LogFile = '{str(log_file).replace("'", "''")}',
    [Parameter(Mandatory=$false)][string]$ExpectedVersion = '{expected_version.replace(chr(39), chr(39) * 2)}',
    [Parameter(Mandatory=$false)][string]$ReadyFile = '{str(ready_file or "").replace(chr(39), chr(39) * 2)}'
)
$ErrorActionPreference = "Stop"

function Write-Log($msg) {{
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $line = "$timestamp [ACTUALIZADOR] $msg"
    Write-Host $line
    if ($LogFile) {{
        try {{
            $dir = Split-Path -Parent $LogFile
            if (-not (Test-Path $dir)) {{ New-Item -ItemType Directory -Path $dir -Force | Out-Null }}
            Add-Content -Path $LogFile -Value $line -Encoding utf8
        }} catch {{}}
    }}
}}

trap {{
    Write-Log "ERROR no controlado: $($_.Exception.Message)"
    exit 1
}}
# El registro existe antes de cargar WinForms; también diagnostica fallos tempranos.
Write-Log "Iniciando actualización de ConXml $ExpectedVersion para PID $ParentPid hacia $TargetDir"
$env:PYINSTALLER_RESET_ENVIRONMENT = "1"
try {{
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
}} catch {{
    Write-Log "No se pudo abrir el progreso: $($_.Exception.Message). Continuando con registro."
    $form = $null
}}

function Set-UpdateStatus($message, $percent = -1) {{
    if ($null -ne $form) {{
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
    }}
    Write-Log $message
}}

function Show-UpdateFailure($message) {{
    Write-Log "ERROR: $message"
    if ($null -ne $form -and ${str(show_completion).lower()}) {{
        [System.Windows.Forms.MessageBox]::Show("$message`n`nRevisa el diagnóstico en:`n$LogFile", "No se pudo actualizar ConXml", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
    }}
    if ($null -ne $form) {{ $form.Close() }}
}}

function Get-InstalledVersion($cliExe) {{
    $version = (& $cliExe --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {{ throw "Falló la consulta de versión del CLI." }}
    return $version
}}

function Get-VerifiedSha256($path) {{
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($path)
    try {{
        return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace("-", "")
    }} finally {{
        $stream.Dispose()
        $sha.Dispose()
    }}
}}

function Copy-WithRetry($source, $destination) {{
    for ($attempt = 1; $attempt -le 30; $attempt++) {{
        try {{
            Copy-Item -LiteralPath $source -Destination $destination -Force -ErrorAction Stop
            if ((Get-VerifiedSha256 $source) -ne (Get-VerifiedSha256 $destination)) {{
                throw "El archivo copiado no coincide con el original."
            }}
            return
        }} catch {{
            if ($attempt -eq 30) {{ throw }}
            Write-Log "Copia bloqueada ($attempt/30): $destination; $($_.Exception.Message)"
            Start-Sleep -Milliseconds 500
        }}
    }}
}}

# Conservar los objetos Process permite comprobar identidad aunque Windows reuse un PID.
$script:launched = @{{}}
function Update-LaunchedProcesses {{
    $snapshot = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    do {{
        $added = $false
        foreach ($item in $snapshot) {{
            $id = [int]$item.ProcessId
            $parent = $script:launched[[int]$item.ParentProcessId]
            if ($null -ne $parent -and -not $script:launched.ContainsKey($id)) {{
                if ($item.ExecutablePath -ne $nuevoExe) {{ continue }}
                try {{
                    if ($item.CreationDate -lt $parent.StartTime) {{ continue }}
                    $child = Get-Process -Id $id -ErrorAction Stop
                    $null = $child.Handle
                    $script:launched[$id] = $child
                    $added = $true
                }} catch {{}}
            }}
        }}
    }} while ($added)
}}

function Stop-LaunchedProcesses {{
    if ($script:launched.Count -eq 0) {{ return }}
    # Si no se puede enumerar el árbol, no sobrescribir binarios todavía en uso.
    Update-LaunchedProcesses
    $processes = @($script:launched.Values | Sort-Object StartTime -Descending)
    foreach ($process in $processes) {{
        if (-not $process.HasExited) {{
            try {{ $process.Kill() }} catch {{
                if (-not $process.HasExited) {{ throw }}
            }}
        }}
    }}
    foreach ($process in $processes) {{
        if (-not $process.WaitForExit(15000)) {{ throw "No terminó PID $($process.Id)." }}
    }}
}}

$backedUp = @()
$changed = @()
function Restore-Backup {{
    try {{
        Stop-LaunchedProcesses
        foreach ($file in $changed) {{
            $destination = Join-Path $TargetDir $file
            if ($backedUp -contains $file) {{
                Copy-WithRetry (Join-Path $BackupDir $file) $destination
            }} else {{
                Remove-Item -LiteralPath $destination -Force -ErrorAction SilentlyContinue
                if (Test-Path -LiteralPath $destination) {{ throw "No se pudo retirar $destination" }}
            }}
        }}
        Write-Log "Rollback verificado. Relanzando versión anterior."
        Start-Process -FilePath (Join-Path $TargetDir "conxml.exe") -WorkingDirectory $TargetDir
        return $true
    }} catch {{
        Write-Log "ERROR crítico durante rollback: $($_.Exception.Message). Respaldo conservado en $BackupDir. No se relanza."
        return $false
    }}
}}

Set-UpdateStatus "Cerrando ConXml para instalar la actualización..."
if ($ReadyFile) {{ Set-Content -LiteralPath $ReadyFile -Value "ready" -Encoding ascii }}

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

{WAIT_INSTALLED_PROCESSES}
try {{
    Wait-InstalledProcesses
}} catch {{
    Show-UpdateFailure "No se pueden sustituir los ejecutables: $($_.Exception.Message)"
    exit 1
}}

# 2. Respaldar todo antes de reemplazar; nunca restaurar un respaldo de otra corrida.
Set-UpdateStatus "Guardando respaldo de la versión anterior..." 15
$archivos = @("conxml.exe", "conxml-cli.exe")
try {{
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    foreach ($f in $archivos) {{
        $origen = Join-Path $StagingDir $f
        if (-not (Test-Path -LiteralPath $origen -PathType Leaf) -or
            (Get-Item -LiteralPath $origen).Length -le 0) {{
            throw "El paquete no contiene un $f válido."
        }}
    }}
    foreach ($f in $archivos) {{
        $actual = Join-Path $TargetDir $f
        if (Test-Path -LiteralPath $actual) {{
            Copy-WithRetry $actual (Join-Path $BackupDir $f)
            $backedUp += $f
            Write-Log "Respaldado $f en $BackupDir"
        }}
    }}
}} catch {{
    Show-UpdateFailure "No se pudo preparar el respaldo. No se cambiaron los archivos: $($_.Exception.Message)"
    exit 1
}}

# 3. Reemplazar, incluyendo en rollback una copia que haya quedado incompleta.
try {{
    foreach ($f in $archivos) {{
        $origen = Join-Path $StagingDir $f
        if (Test-Path -LiteralPath $origen) {{
            Set-UpdateStatus "Instalando $f..." 45
            $changed += $f
            Copy-WithRetry $origen (Join-Path $TargetDir $f)
            Write-Log "Instalado $f"
        }}
    }}

    # Confirmar que el ZIP instalado reporta la versión esperada.
    $cliExe = Join-Path $TargetDir "conxml-cli.exe"
    $versionInstalada = Get-InstalledVersion $cliExe
    if ($versionInstalada -ne "conxml $ExpectedVersion") {{
        throw "Se esperaba conxml $ExpectedVersion y el ejecutable instalado reportó '$versionInstalada'."
    }}
    Write-Log "Versión comprobada antes del arranque: $versionInstalada"

    # 4. PyInstaller onefile abre la GUI en un hijo del bootloader.
    $nuevoExe = Join-Path $TargetDir "conxml.exe"
    Set-UpdateStatus "Iniciando ConXml $ExpectedVersion para comprobar la actualización..." 85
    $nuevoProc = Start-Process -FilePath $nuevoExe -WorkingDirectory $TargetDir -PassThru
    $null = $nuevoProc.Handle
    $script:launched[$nuevoProc.Id] = $nuevoProc
    $ventanaAbierta = $false
    for ($i = 0; $i -lt 120; $i++) {{
        Update-LaunchedProcesses
        foreach ($process in @($script:launched.Values)) {{
            $process.Refresh()
            if (-not $process.HasExited -and $process.MainWindowHandle -ne [IntPtr]::Zero) {{
                Write-Log "Ventana detectada en PID $($process.Id) (lanzador $($nuevoProc.Id))."
                $ventanaAbierta = $true
                break
            }}
        }}
        if ($ventanaAbierta) {{ break }}
        if ($null -ne $form) {{ [System.Windows.Forms.Application]::DoEvents() }}
        Start-Sleep -Milliseconds 500
    }}
    if (-not $ventanaAbierta) {{ throw "ConXml $ExpectedVersion no abrió una ventana en 60 segundos." }}
}} catch {{
    Write-Log "ERROR de actualización: $($_.Exception.Message). Iniciando rollback."
    if (Restore-Backup) {{
        Show-UpdateFailure "No se completó la actualización. Se restauró y relanzó la versión anterior."
    }} else {{
        Show-UpdateFailure "No se completó la restauración. No se relanzó ConXml. Conserva el respaldo en $BackupDir y consulta el registro."
    }}
    exit 1
}}

# 5. Limpieza de staging
try {{
    Remove-Item -LiteralPath $StagingDir -Recurse -Force -ErrorAction SilentlyContinue
}} catch {{}}

Set-UpdateStatus "ConXml $ExpectedVersion se abrió correctamente. Actualización completada." 100
Write-Log "Actualización completada exitosamente."
if ($null -ne $form -and ${str(show_completion).lower()}) {{
[System.Windows.Forms.MessageBox]::Show("ConXml se actualizó a la versión $ExpectedVersion y se abrió correctamente.", "Actualización completada", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
$form.Close()
}}
if ($null -ne $form) {{ $form.Close() }}
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
        if ruta.name in encontrados:
            raise UpdateError("El paquete contiene un ejecutable duplicado.")
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

    if encontrados != permitidos:
        raise UpdateError("El paquete debe contener conxml.exe y conxml-cli.exe.")


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

        backup_root = self.cache / "backup"
        backup_root.mkdir(parents=True, exist_ok=True)
        backup_dir = Path(tempfile.mkdtemp(prefix="attempt-", dir=backup_root))
        log_file = Config().logs_dir / "actualizacion.log"
        script_path = self.cache / "actualizar.ps1"
        ready_file = backup_dir / "helper.ready"

        generar_script_actualizador(
            script_path,
            parent_pid=parent_pid or os.getpid(),
            target_dir=target_dir,
            staging_dir=staging_dir,
            backup_dir=backup_dir,
            log_file=log_file,
            expected_version=release.version,
            ready_file=ready_file,
        )

        if sys.platform == "win32" and not self.demo and getattr(sys, "frozen", False):
            self._start_helper(script_path, ready_file, log_file, release.version)

        return script_path

    def _start_helper(self, script_path: Path, ready_file: Path, log_file: Path, version: str):
        # Persistir también errores de parser/arranque, anteriores a Write-Log.
        log_file.parent.mkdir(parents=True, exist_ok=True)
        launch_log = log_file.with_name("actualizacion-launcher.log")
        with launch_log.open("ab", buffering=0) as output:
            output.write(f"\nLanzando actualización {version}: {script_path}\n".encode("utf-8"))
            helper = launch_powershell(script_path, self.cache, output)
        deadline = time.monotonic() + 15
        while not ready_file.is_file():
            if helper.poll() is not None:
                raise UpdateError(f"El actualizador terminó antes de iniciar (código {getattr(helper, "returncode", "desconocido")}). Revisa {launch_log}")
            if time.monotonic() >= deadline:
                helper.terminate()
                helper.wait(timeout=5)
                raise UpdateError(f"El actualizador no confirmó su arranque. Revisa {launch_log}")
            time.sleep(0.1)
        if helper.poll() is not None:
            raise UpdateError(f"El actualizador terminó después de confirmar su arranque (código {getattr(helper, "returncode", "desconocido")}). Revisa {launch_log}")


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
        self.cache.mkdir(parents=True, exist_ok=True)
        attempt = Path(tempfile.mkdtemp(prefix="setup-", dir=self.cache))
        helper = attempt / "instalar.ps1"
        ready_file = attempt / "helper.ready"
        log_file = Config().logs_dir / "actualizacion-setup.log"
        target = Path(sys.executable).resolve().parent
        quote = lambda value: str(value).replace("'", "''")
        helper.write_text(
            "$ErrorActionPreference = 'Stop'\n"
            f"$installer = '{quote(path)}'\n"
            f"$TargetDir = '{quote(target)}'\n"
            f"$LogFile = '{quote(log_file)}'\n"
            "$env:PYINSTALLER_RESET_ENVIRONMENT = '1'\n"
            "try {\n"
            f"    Set-Content -LiteralPath '{quote(ready_file)}' -Value 'ready' -Encoding ascii\n"
            f"    Wait-Process -Id {os.getpid()} -Timeout 60 -ErrorAction SilentlyContinue\n"
            + WAIT_INSTALLED_PROCESSES + "\n"
            "    Wait-InstalledProcesses\n"
            # Fijar destino para evitar actualizar otra instalación del registro.
            '    $arguments = @("/DIR=`"$TargetDir`"", "/LOG=`"$LogFile`"")\n'
            "    $setup = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru\n"
            "    if ($setup.ExitCode -ne 0) { throw \"Setup terminó con código $($setup.ExitCode). Instalador conservado: $installer\" }\n"
            "} catch {\n"
            "    $failure = $_.Exception.Message\n"
            "    Write-Output $failure\n"
            "    try { Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show(\"$failure`nRegistro: $LogFile\", 'No se pudo actualizar ConXml') | Out-Null } catch {}\n"
            "    exit 1\n"
            "}\n",
            encoding="utf-8-sig",
        )
        self._start_helper(helper, ready_file, log_file, release.version)
