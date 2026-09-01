# -*- mode: python ; coding: utf-8 -*-
# Spec de PyInstaller para ConXml (Windows):
#   conxml.exe      -> interfaz gráfica (ventana, sin consola)
#   conxml-cli.exe  -> línea de comandos (consola)
# Uso: python -m PyInstaller --noconfirm --clean conxml.spec

excludes = ["pytest", "_pytest", "tests"]

ICONO = "src/conxml/ui/assets/logo_conxml.ico"
ICONO_PNG = "src/conxml/ui/assets/logo_conxml.png"

a_gui = Analysis(
    ["src/conxml/ui_main.py"],
    pathex=["src"],
    binaries=[],
    datas=[(ICONO, "assets"), (ICONO_PNG, "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

a_cli = Analysis(
    ["src/conxml/cli.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz_gui = PYZ(a_gui.pure)
pyz_cli = PYZ(a_cli.pure)

exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    a_gui.binaries,
    a_gui.datas,
    [],
    name="conxml",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=ICONO,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    a_cli.binaries,
    a_cli.datas,
    [],
    name="conxml-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon=ICONO,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)