# Prueba los artefactos reales: Setup -> app instalada -> helper -> nueva app.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$py = Join-Path $root '.venv\Scripts\python.exe'
$version = & $py -c 'from conxml import __version__; print(__version__)'
$testRoot = Join-Path $root 'dist\update-smoke'
$target = Join-Path $testRoot "app [prueba]'á"
$env:CONXML_DATA_DIR = Join-Path $testRoot 'data'
$env:CONXML_LOG_DIR = Join-Path $testRoot 'logs'
$env:CONXML_SMOKE_TARGET = $target
$env:CONXML_SMOKE_ROOT = $testRoot
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
$setup = Join-Path $root "dist\installer\ConXml-Setup-$version-windows-x64.exe"
$install = Start-Process -FilePath $setup -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', "/DIR=`"$target`"", "/LOG=`"$testRoot\setup.log`"") -Wait -PassThru
if ($install.ExitCode -ne 0) { throw "Falló Setup: $($install.ExitCode)" }
$installedVersion = & (Join-Path $target 'conxml-cli.exe') --version
if ($LASTEXITCODE -ne 0 -or $installedVersion.Trim() -ne "conxml $version") { throw 'Versión instalada incorrecta' }
New-Item -ItemType Directory -Path $env:CONXML_DATA_DIR -Force | Out-Null
$sentinel = Join-Path $env:CONXML_DATA_DIR 'conservar.txt'
Set-Content -LiteralPath $sentinel -Value 'datos intactos'
$prepare = @'
from conxml.config import Config
from conxml.catalog.db import Catalogo
from conxml.estado_local import guardar
Config().inicializar()
with Catalogo(Config().db_path) as catalogo:
    catalogo.crear_cliente('SMOKE', 'Prueba instalador', 'EKU9003173C9')
guardar({'sesion': {'cliente': 'SMOKE'}})
'@
& $py -c $prepare
if ($LASTEXITCODE -ne 0) { throw 'No se preparó la sesión de prueba' }
$old = Start-Process -FilePath (Join-Path $target 'conxml.exe') -PassThru
$env:CONXML_SMOKE_PID = "$($old.Id)"
$helper = $null
try {
    # Staging usa los binarios recién compilados; la prueba verifica reaplicación,
    # cierre real del bootloader, copia, versión CLI y apertura de GUI.
    $code = @'
import os, shutil
from pathlib import Path
from conxml import __version__
from conxml.updates import generar_script_actualizador
root = Path(os.environ['CONXML_SMOKE_ROOT'])
staging = root / 'staging'
staging.mkdir(exist_ok=True)
for name in ('conxml.exe', 'conxml-cli.exe'):
    shutil.copy2(Path('dist') / name, staging / name)
print(generar_script_actualizador(root / 'update.ps1',
    parent_pid=int(os.environ['CONXML_SMOKE_PID']),
    target_dir=Path(os.environ['CONXML_SMOKE_TARGET']), staging_dir=staging,
    backup_dir=root / 'backup', log_file=root / 'update.log',
    expected_version=__version__, ready_file=root / 'ready', show_completion=False))
'@
    $script = & $py -c $code
    if ($LASTEXITCODE -ne 0) { throw 'No se generó el helper' }
    $helper = Start-Process powershell.exe -ArgumentList @('-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass', '-File', "`"$script`"") -PassThru
    $deadline = (Get-Date).AddSeconds(20)
    do {
        $appProcesses = @(Get-Process | Where-Object { $_.Path -eq (Join-Path $target 'conxml.exe') })
        $windows = @($appProcesses | Where-Object { $_.MainWindowHandle -ne 0 })
        if ($windows.Count -gt 0) { break }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    if ($windows.Count -eq 0) { throw 'La instalación inicial no abrió la GUI' }
    foreach ($window in $windows) { $null = $window.CloseMainWindow() }
    if (-not $helper.WaitForExit(120000)) { throw 'Timeout del helper' }
    if ($helper.ExitCode -ne 0) { throw 'Falló actualización: consultar update.log' }
    if ((Get-Content -LiteralPath $sentinel -Raw).Trim() -ne 'datos intactos') { throw 'Datos modificados' }
    foreach ($name in @('conxml.exe', 'conxml-cli.exe')) {
        if ((Get-FileHash -LiteralPath (Join-Path $target $name)).Hash -ne (Get-FileHash -LiteralPath (Join-Path $root "dist\$name")).Hash) { throw "Copia incorrecta: $name" }
    }
    Write-Host 'Setup, cierre onefile, reemplazo, versión, GUI y datos: OK'
} finally {
    if ($helper -and -not $helper.HasExited) { Stop-Process -Id $helper.Id -Force }
    Get-Process | Where-Object { $_.Path -eq (Join-Path $target 'conxml.exe') } | Stop-Process -Force
}
