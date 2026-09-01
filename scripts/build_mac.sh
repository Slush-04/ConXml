#!/usr/bin/env bash
# Construye la aplicación nativa ConXml.app y el binario CLI para macOS
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "==> Iniciando proceso de compilación para macOS..."

# 1. Detectar entorno virtual de Python
PY=""
if [ -f "$ROOT_DIR/.venv-mac/bin/python" ]; then
    PY="$ROOT_DIR/.venv-mac/bin/python"
elif [ -f "$ROOT_DIR/.venv/bin/python" ]; then
    PY="$ROOT_DIR/.venv/bin/python"
elif command -v python3 &> /dev/null; then
    PY="$(command -v python3)"
else
    echo "ERROR: No se encontró Python 3. Crea o activa un entorno virtual primero."
    exit 1
fi

echo "==> Usando intérprete: $PY ($($PY --version))"

# 2. Verificar o instalar PyInstaller
if ! "$PY" -c "import PyInstaller" &> /dev/null; then
    echo "==> Instalando PyInstaller en el entorno..."
    "$PY" -m pip install --quiet pyinstaller
fi

# 3. Generar icono .icns si no existe
ICNS_PATH="src/conxml/ui/assets/logo_conxml.icns"
PNG_PATH="src/conxml/ui/assets/logo_conxml.png"

if [ ! -f "$ICNS_PATH" ] && [ -f "$PNG_PATH" ]; then
    echo "==> Generando icono de macOS ($ICNS_PATH)..."
    ICONSET_DIR="/tmp/conxml_logo.iconset"
    mkdir -p "$ICONSET_DIR"
    sips -z 16 16     "$PNG_PATH" --out "$ICONSET_DIR/icon_16x16.png" > /dev/null 2>&1
    sips -z 32 32     "$PNG_PATH" --out "$ICONSET_DIR/icon_16x16@2x.png" > /dev/null 2>&1
    sips -z 32 32     "$PNG_PATH" --out "$ICONSET_DIR/icon_32x32.png" > /dev/null 2>&1
    sips -z 64 64     "$PNG_PATH" --out "$ICONSET_DIR/icon_32x32@2x.png" > /dev/null 2>&1
    sips -z 128 128   "$PNG_PATH" --out "$ICONSET_DIR/icon_128x128.png" > /dev/null 2>&1
    sips -z 256 256   "$PNG_PATH" --out "$ICONSET_DIR/icon_128x128@2x.png" > /dev/null 2>&1
    sips -z 256 256   "$PNG_PATH" --out "$ICONSET_DIR/icon_256x256.png" > /dev/null 2>&1
    iconutil -c icns "$ICONSET_DIR" -o "$ICNS_PATH"
    rm -rf "$ICONSET_DIR"
fi

# 4. Compilar con PyInstaller
echo "==> Compilando ConXml con PyInstaller..."
"$PY" -m PyInstaller --noconfirm --clean conxml.spec

# 5. Validar artefactos generados
APP_PATH="$ROOT_DIR/dist/ConXml.app"
CLI_PATH="$ROOT_DIR/dist/conxml-cli"

if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: No se generó la aplicación $APP_PATH"
    exit 1
fi

echo ""
echo "============================================================"
echo "✅ Compilación exitosa para macOS:"
echo "   - App gráfica: $APP_PATH"
echo "   - CLI consola: $CLI_PATH"
echo ""
echo "Notas de uso en macOS:"
echo "1. Puedes mover 'ConXml.app' a tu carpeta /Applications."
echo "2. Los datos y catálogo SQLite se guardarán de forma segura en:"
echo "   ~/Library/Application Support/ConXml/"
echo "3. Si macOS muestra aviso de 'desarrollador no identificado':"
echo "   Haz clic derecho sobre ConXml.app -> Abrir (solo la primera vez)"
echo "   o ejecuta en terminal: xattr -cr \"$APP_PATH\""
echo "============================================================"
