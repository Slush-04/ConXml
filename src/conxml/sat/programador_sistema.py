"""Registro del ejecutor SAT sin interfaz en el programador del usuario."""
from __future__ import annotations

import hashlib
import os
import plistlib
import subprocess
import sys
from pathlib import Path

from conxml.config import Config


def identificador(config: Config) -> str:
    return 'com.conxml.sat.' + hashlib.sha256(str(config.base).encode()).hexdigest()[:12]


def comando(config: Config) -> list[str]:
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--sat-periodico', '--datos', str(config.base)]
    python = Path(sys.executable)
    if sys.platform == 'win32' and python.with_name('pythonw.exe').is_file():
        python = python.with_name('pythonw.exe')
    return [str(python), '-m', 'conxml.sat.periodicas', '--datos', str(config.base)]


def _ejecutar(args, *, comprobar=True):
    salida = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if comprobar and salida.returncode:
        raise OSError('El programador del sistema rechazó el registro de ConXml. Revisa los permisos de tareas en segundo plano.')
    return salida


def instalar(config: Config) -> None:
    nombre, args = identificador(config), comando(config)
    # El código local usa una instalación editable; PYTHONPATH cubre también
    # lanzadores ejecutados por el sistema fuera del directorio del proyecto.
    fuente = str(Path(__file__).resolve().parents[2])
    if sys.platform == 'darwin':
        carpeta = Path.home() / 'Library' / 'LaunchAgents'
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / (nombre + '.plist')
        config.logs_dir.mkdir(parents=True, exist_ok=True)
        contenido = {
            'Label': nombre, 'ProgramArguments': args,
            'StartInterval': 60, 'RunAtLoad': True,
            'EnvironmentVariables': {'PYTHONPATH': fuente},
            'StandardErrorPath': str(config.logs_dir / 'sat-periodico.log'),
        }
        if ruta.exists():
            anterior = plistlib.loads(ruta.read_bytes())
            if anterior == contenido:
                estado = _ejecutar(['launchctl', 'print', f'gui/{os.getuid()}/{nombre}'], comprobar=False)
                if estado.returncode == 0:
                    return
            else:
                _ejecutar(['launchctl', 'bootout', f'gui/{os.getuid()}', str(ruta)], comprobar=False)
        ruta.write_bytes(plistlib.dumps(contenido))
        ruta.chmod(0o600)
        _ejecutar(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(ruta)])
    elif sys.platform == 'win32':
        _ejecutar(['schtasks', '/Create', '/TN', nombre, '/TR', subprocess.list2cmdline(args),
                   '/SC', 'MINUTE', '/MO', '1', '/IT', '/F'])
    else:
        carpeta = Path.home() / '.config' / 'systemd' / 'user'
        carpeta.mkdir(parents=True, exist_ok=True)
        def citar(valor):
            return '"' + valor.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
        (carpeta / (nombre + '.service')).write_text(
            '[Unit]\nDescription=ConXml SAT periódico\n[Service]\nType=oneshot\n'
            + 'Environment=' + citar('PYTHONPATH=' + fuente) + '\n'
            + 'ExecStart=' + ' '.join(citar(a) for a in args) + '\n', encoding='utf-8')
        (carpeta / (nombre + '.timer')).write_text(
            '[Unit]\nDescription=ConXml SAT periódico\n[Timer]\nOnCalendar=*-*-* *:*:00\n'
            'Persistent=true\n[Install]\nWantedBy=timers.target\n', encoding='utf-8')
        _ejecutar(['systemctl', '--user', 'daemon-reload'])
        _ejecutar(['systemctl', '--user', 'enable', '--now', nombre + '.timer'])


def desinstalar(config: Config) -> None:
    nombre = identificador(config)
    if sys.platform == 'darwin':
        ruta = Path.home() / 'Library' / 'LaunchAgents' / (nombre + '.plist')
        if ruta.exists():
            _ejecutar(['launchctl', 'bootout', f'gui/{os.getuid()}', str(ruta)], comprobar=False)
            ruta.unlink()
    elif sys.platform == 'win32':
        _ejecutar(['schtasks', '/Delete', '/TN', nombre, '/F'], comprobar=False)
    else:
        _ejecutar(['systemctl', '--user', 'disable', '--now', nombre + '.timer'], comprobar=False)
        carpeta = Path.home() / '.config' / 'systemd' / 'user'
        for extension in ('.service', '.timer'):
            (carpeta / (nombre + extension)).unlink(missing_ok=True)
        _ejecutar(['systemctl', '--user', 'daemon-reload'])
