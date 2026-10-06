# Windows x64, Python 3.13 x64 e Inno Setup 6.3+.
param([string]$ISCC = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    py -3.13 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Instala Python 3.13 x64." }
}
& $py -m pip install -e '.[dev]' pyinstaller
if ($LASTEXITCODE -ne 0) { throw "No se instalaron las dependencias." }
& $py scripts/release_version.py --check
if ($LASTEXITCODE -ne 0) { throw "Versiones inconsistentes." }
& $py -m pytest
if ($LASTEXITCODE -ne 0) { throw "Fallaron las pruebas." }
& "$PSScriptRoot\build_exe.ps1"
$version = & $py -c 'from conxml import __version__; print(__version__)'

# Empaquetar artefacto ZIP para actualización directa sin instalador
$zipPath = Join-Path $root "dist\ConXml-$version-windows-x64.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "$root\dist\conxml.exe", "$root\dist\conxml-cli.exe" -DestinationPath $zipPath -Force
$zipHash = (Get-FileHash -Algorithm SHA256 $zipPath).Hash.ToLower()
"$zipHash  $(Split-Path -Leaf $zipPath)" | Set-Content -Encoding ascii "$zipPath.sha256"
Write-Host "Paquete actualizable listo: $zipPath"

if (-not (Test-Path $ISCC)) { throw "Instala Inno Setup 6.3+ o pasa -ISCC ruta." }
& $ISCC "/DAppVersion=$version" installer\conxml.iss
if ($LASTEXITCODE -ne 0) { throw "Falló el instalador." }
$exe = Join-Path $root "dist\installer\ConXml-Setup-$version-windows-x64.exe"
if (-not (Test-Path $exe)) { throw "Falta el instalador." }
$hash = (Get-FileHash -Algorithm SHA256 $exe).Hash.ToLower()
"$hash  $(Split-Path -Leaf $exe)" | Set-Content -Encoding ascii "$exe.sha256"
Write-Host "Instalador listo: $exe"
