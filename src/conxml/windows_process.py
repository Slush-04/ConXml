"""Launch a system PowerShell from the Windows PyInstaller application."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import BinaryIO


def launch_powershell(script: Path, cwd: Path, output: BinaryIO) -> subprocess.Popen:
    """Start the helper without inheriting PyInstaller's DLL search directory."""
    if os.name == "nt":
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    else:
        powershell = Path("powershell.exe")
    cmd = [
        str(powershell), "-NoProfile", "-NonInteractive", "-STA",
        "-ExecutionPolicy", "Bypass", "-File", str(script),
    ]
    env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    bundle_dir = getattr(sys, "_MEIPASS", None) if getattr(sys, "frozen", False) else None
    if bundle_dir and os.name == "nt":
        bundle = os.path.normcase(os.path.abspath(bundle_dir))
        env["PATH"] = os.pathsep.join(
            entry for entry in env.get("PATH", "").split(os.pathsep)
            if entry and not (
                os.path.normcase(os.path.abspath(entry)) == bundle
                or os.path.normcase(os.path.abspath(entry)).startswith(bundle + os.sep)
            )
        )
        # PyInstaller's SetDllDirectoryW setting is inherited by subprocesses.
        # System PowerShell must search for system DLLs while it starts.
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        set_dll_dir = kernel32.SetDllDirectoryW
        set_dll_dir.argtypes = [ctypes.c_wchar_p]
        set_dll_dir.restype = ctypes.c_bool
        if not set_dll_dir(None):
            raise OSError(ctypes.get_last_error(), "No se pudo restaurar la ruta DLL del sistema")
        try:
            return subprocess.Popen(
                cmd, creationflags=flags, close_fds=True, stdin=subprocess.DEVNULL,
                stdout=output, stderr=subprocess.STDOUT, cwd=str(cwd), env=env,
            )
        finally:
            set_dll_dir(bundle_dir)
    return subprocess.Popen(
        cmd, creationflags=flags, close_fds=True, stdin=subprocess.DEVNULL,
        stdout=output, stderr=subprocess.STDOUT, cwd=str(cwd), env=env,
    )
