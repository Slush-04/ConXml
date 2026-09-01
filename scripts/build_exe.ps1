# Construye el ejecutable independiente conxml.exe (Windows, onefile)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
    throw "No existe .venv\Scripts\python.exe. Crea el entorno virtual primero."
}

Write-Host "==> Instalando PyInstaller en .venv"
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Fallo al instalar PyInstaller." }

Write-Host "==> Compilando conxml.exe (onefile)"
& $py -m PyInstaller --noconfirm --clean conxml.spec
if ($LASTEXITCODE -ne 0) { throw "Fallo al compilar conxml.exe." }

$exe = Join-Path $root "dist\conxml.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "No se generó $exe." }

$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "OK: $exe  ($size MB)"
Write-Host "    $root\dist\conxml-cli.exe  (CLI, consola)"
Write-Host "Nota: el exe crea la carpeta 'data' junto a sí mismo (BD SQLite y salidas)."