# -*- mode: python ; coding: utf-8 -*-
# Spec de PyInstaller multiplataforma para ConXml:
#   - En Windows: genera conxml.exe (GUI) y conxml-cli.exe (consola)
#   - En macOS:   genera ConXml.app (GUI nativa .app) y conxml-cli (consola)
# Uso: python -m PyInstaller --noconfirm --clean conxml.spec

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

excludes = ["pytest", "_pytest", "tests"]

ICONO_ICO = "src/conxml/ui/assets/logo_conxml.ico"
ICONO_PNG = "src/conxml/ui/assets/logo_conxml.png"
ICONO_ICNS = "src/conxml/ui/assets/logo_conxml.icns"

icono_principal = ICONO_ICNS if (sys.platform == "darwin" and os.path.exists(ICONO_ICNS)) else ICONO_ICO

datas_gui = [
    (ICONO_ICO, "assets"),
    (ICONO_PNG, "assets"),
]
if os.path.exists(ICONO_ICNS):
    datas_gui.append((ICONO_ICNS, "assets"))

# Incluir recursos de CustomTkinter (fuentes, temas JSON)
datas_gui += collect_data_files("customtkinter")

# En macOS no se recomienda UPX porque puede invalidar binarios Mach-O
usar_upx = False if sys.platform == "darwin" else True

a_gui = Analysis(
    ["src/conxml/ui_main.py"],
    pathex=["src"],
    binaries=[],
    datas=datas_gui,
    hiddenimports=["customtkinter", "darkdetect"],
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
    upx=usar_upx,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=icono_principal,
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
    upx=usar_upx,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon=icono_principal,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# En macOS empaquetamos el ejecutable gráfico como ConXml.app
if sys.platform == "darwin":
    app = BUNDLE(
        exe_gui,
        name="ConXml.app",
        icon=icono_principal if os.path.exists(icono_principal) else None,
        bundle_identifier="com.conxml.app",
        info_plist={
            "CFBundleName": "ConXml",
            "CFBundleDisplayName": "ConXml",
            "CFBundleIdentifier": "com.conxml.app",
            "CFBundleVersion": "0.1.0",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": "True",
            "NSRequiresAquaSystemAppearance": "False",
            "LSMinimumSystemVersion": "10.15",
        },
    )