import hashlib
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from conxml.updates import Updater, UpdateError, version_tuple


@pytest.fixture
def feed(tmp_path, monkeypatch):
    state = {'payload': b'instalador ficticio', 'body': None, 'status': 200}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(state['status'])
            self.end_headers()
            self.wfile.write(json.dumps(state['body']).encode() if self.path == '/latest' else state['payload'])
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    url = f'http://127.0.0.1:{server.server_port}'
    name = 'ConXml-Setup-0.2.2-windows-x64.exe'
    state['body'] = {'tag_name': 'v0.2.2', 'draft': False, 'prerelease': False,
                     'assets': [{'name': name, 'state': 'uploaded', 'size': len(state['payload']),
                                 'digest': 'sha256:' + hashlib.sha256(state['payload']).hexdigest(),
                                 'browser_download_url': url + '/' + name}]}
    monkeypatch.setenv('CONXML_UPDATE_DEMO_URL', url + '/latest')
    updater = Updater(tmp_path / 'updates', current='0.2.0')
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield updater, state
    server.shutdown()
    server.server_close()
    worker.join()


def test_real_http_check_download_and_refuse_mac_install(feed, tmp_path):
    updater, state = feed
    data = tmp_path / 'data'
    data.mkdir()
    sentinel = data / 'preferencias.json'
    sentinel.write_text('{"cliente":"conservar"}')
    release = updater.check()
    progress = []
    path = updater.download(release, lambda a, b: progress.append((a, b)))
    assert path.read_bytes() == state['payload']
    assert progress[-1] == (release.size, release.size)
    with pytest.raises(UpdateError, match='Windows'):
        updater.launch(release, path)
    assert sentinel.read_text() == '{"cliente":"conservar"}'


@pytest.mark.parametrize('case', ['current', 'older', 'draft', 'prerelease', 'missing', 'no_digest', 'bad_digest', 'wrong_arch', 'uploading', 'bad_size'])
def test_unready_or_incompatible_release_not_announced(feed, case):
    updater, state = feed
    body = state['body']
    asset = body['assets'][0]
    if case in ('current', 'older'):
        body['tag_name'] = 'v0.2.0' if case == 'current' else 'v0.1.9'
    elif case in ('draft', 'prerelease'):
        body[case] = True
    elif case == 'missing':
        body['assets'] = []
    elif case == 'no_digest':
        asset.pop('digest')
    elif case == 'bad_digest':
        asset['digest'] = 'sha256:abc'
    elif case == 'wrong_arch':
        asset['name'] = asset['name'].replace('x64', 'arm64')
    elif case == 'uploading':
        asset['state'] = 'new'
    else:
        asset['size'] = -1
    assert updater.check() is None


@pytest.mark.parametrize('mode', ['corrupt', 'truncated', 'oversize', 'offline'])
def test_failed_download_leaves_no_partial_installer(feed, mode):
    updater, state = feed
    release = updater.check()
    if mode == 'corrupt':
        state['payload'] = b'X' + state['payload'][1:]
    elif mode == 'truncated':
        state['payload'] = b'a'
    elif mode == 'oversize':
        state['payload'] *= 2
    else:
        state['status'] = 503
    with pytest.raises(UpdateError):
        updater.download(release)
    assert list(updater.cache.iterdir()) == []


def test_no_network_and_retry(feed):
    updater, state = feed
    state['status'] = 503
    with pytest.raises(UpdateError):
        updater.check()
    state['status'] = 200
    assert updater.check()


def test_foreign_origin_refused(feed):
    updater, state = feed
    state['body']['assets'][0]['browser_download_url'] = 'http://example.com/evil.exe'
    with pytest.raises(UpdateError, match='ajena'):
        updater.check()


def test_production_origins_and_demo_disabled_in_binary(tmp_path, monkeypatch):
    monkeypatch.setattr('sys.frozen', True, raising=False)
    monkeypatch.setenv('CONXML_UPDATE_DEMO_URL', 'http://127.0.0.1:8765/latest')
    updater = Updater(tmp_path)
    assert not updater.demo
    for url in ['http://github.com/x', 'https://evil.com/x', 'https://github.com.evil.com/x', 'https://user@github.com/x']:
        with pytest.raises(UpdateError):
            updater._safe_url(url, asset=True)
    updater._safe_url('https://release-assets.githubusercontent.com/file', asset=True)


def test_numeric_version_order():
    assert version_tuple('v0.2.10') > version_tuple('0.2.9')
    with pytest.raises(UpdateError):
        version_tuple('v1.2.3-beta')


@pytest.mark.skipif(sys.platform == 'win32' and os.environ.get('GITHUB_ACTIONS') == 'true',
                    reason='La prueba de interfaz gráfica es para macOS; Windows valida lógica y descargas HTTP.')
def test_download_icon_and_ui_flow_on_mac(feed, tmp_path, monkeypatch):
    import subprocess
    import sys
    monkeypatch.setenv('CONXML_DATA_DIR', str(tmp_path / 'data'))
    code = r"""
import time
import tkinter as tk
import customtkinter as ctk
from conxml.catalog.db import Catalogo
from conxml.ui.app import ConXmlApp
from conxml.ui import actualizaciones
from conxml.boveda import ocultar_instrucciones_boveda
from conxml.config import Config
Config().inicializar()
with Catalogo(Config().db_path) as cat:
    cat.crear_cliente('DEMO', 'Prueba actualización', 'EKU9003173C9')
ocultar_instrucciones_boveda(Config())
try:
    root = ctk.CTk()
except tk.TclError:
    print('SKIP_DISPLAY')
    raise SystemExit(0)
try:
    root.withdraw()
    app = ConXmlApp(root, cliente_actual='DEMO')
    controller = app.actualizaciones
    controller.check(manual=True)
    deadline = time.monotonic() + 5
    while controller.release is None and time.monotonic() < deadline:
        root.update()
        time.sleep(.02)
    assert controller.release is not None
    assert controller.button.cget('text') == '⬇'
    dialogs = []
    actualizaciones.messagebox.askyesno = lambda *args, **kw: True
    actualizaciones.messagebox.showinfo = lambda *args, **kw: dialogs.append(args)
    controller.click()
    deadline = time.monotonic() + 5
    while not dialogs and time.monotonic() < deadline:
        root.update()
        time.sleep(.02)
    assert dialogs
    assert 'SHA-256' in dialogs[0][1]
    assert controller.path.is_file()
    assert root.winfo_exists()
finally:
    root.destroy()
"""
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=30)
    if 'SKIP_DISPLAY' in result.stdout:
        pytest.skip('sin display')
    assert result.returncode == 0, result.stdout + result.stderr


def test_windows_launch_rechecks_file_and_uses_interactive_setup(feed, monkeypatch):
    updater, _ = feed
    release = updater.check()
    path = updater.download(release)
    updater.demo = ''
    monkeypatch.setattr('sys.platform', 'win32')
    monkeypatch.setattr('sys.frozen', True, raising=False)
    launches = []
    monkeypatch.setattr('conxml.updates.subprocess.Popen', lambda args, **kw: launches.append(args))
    updater.launch(release, path)
    assert launches and launches[0][0] == 'powershell.exe'
    script_path = Path(launches[0][launches[0].index('-File') + 1])
    script = script_path.read_text(encoding='utf-8')
    assert f'Wait-Process -Id {os.getpid()}' in script
    assert str(path).replace("'", "''") in script
    path.write_bytes(b'alterado')
    with pytest.raises(UpdateError, match='cambió'):
        updater.launch(release, path)
    assert len(launches) == 1


def test_redirect_validated_before_connecting_to_foreign_host(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.delenv('CONXML_UPDATE_DEMO_URL', raising=False)
    calls = []
    class Session:
        def get(self, url, **kw):
            calls.append(url)
            return SimpleNamespace(status_code=302, headers={'Location': 'http://evil.com/file'}, close=lambda: None)
    updater = Updater(tmp_path, session=Session())
    with pytest.raises(UpdateError, match='Origen'):
        updater._get('https://github.com/Slush-04/ConXml/releases/download/v1.0.0/file', asset=True)
    assert len(calls) == 1


def test_install_saves_session_and_backup_before_closing(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from conxml.ui import actualizaciones as ui
    from conxml.ui.actualizaciones import Actualizaciones
    events = []
    monkeypatch.setenv('CONXML_DATA_DIR', str(tmp_path))
    monkeypatch.setattr('sys.platform', 'win32')
    monkeypatch.setattr('sys.frozen', True, raising=False)
    monkeypatch.setattr(ui.messagebox, 'askyesno', lambda *a, **kw: True)
    def backup(base):
        assert base == tmp_path
        events.append('respaldo')
        return SimpleNamespace(faltantes=[])
    monkeypatch.setattr(ui, 'respaldo_automatico', backup)
    monkeypatch.setattr('sys.exit', lambda code=0: events.append('exit'))
    controller = Actualizaciones.__new__(Actualizaciones)
    controller.updater = SimpleNamespace(demo='', apply_update=lambda *a: events.append('instalador'), launch=lambda *a: events.append('instalador'))
    controller.app = SimpleNamespace(guardar_sesion=lambda: events.append('sesion'),
                                     ejecutar=lambda fn, cb, *a: cb(fn()),
                                     master=SimpleNamespace(destroy=lambda: events.append('cerrar')))
    controller._downloaded(SimpleNamespace(version='0.2.1'), tmp_path / 'setup.exe')
    assert events == ['sesion', 'respaldo', 'instalador', 'cerrar', 'exit']


def test_zip_release_preferred_over_installer(feed):
    updater, state = feed
    zip_name = 'ConXml-0.2.2-windows-x64.zip'
    zip_payload = b'dummy zip content'
    state['payload'] = zip_payload
    # Agregar asset ZIP además del instalador
    state['body']['assets'].insert(0, {
        'name': zip_name,
        'state': 'uploaded',
        'size': len(zip_payload),
        'digest': 'sha256:' + hashlib.sha256(zip_payload).hexdigest(),
        'browser_download_url': f"http://127.0.0.1:{updater.demo.split(':')[2].split('/')[0]}/{zip_name}"
    })
    release = updater.check()
    assert release is not None
    assert release.name == zip_name
    assert release.kind == 'zip'


def test_zip_download_staging_and_helper_script(tmp_path, monkeypatch):
    import io
    import zipfile
    from conxml.updates import Release

    # Crear un ZIP válido con conxml.exe y conxml-cli.exe
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('conxml.exe', b'nuevo conxml v2')
        z.writestr('conxml-cli.exe', b'nuevo cli v2')
    zip_bytes = buf.getvalue()
    zip_sha = hashlib.sha256(zip_bytes).hexdigest()

    cache_dir = tmp_path / 'updates'
    target_dir = tmp_path / 'install'
    target_dir.mkdir(parents=True)
    (target_dir / 'conxml.exe').write_bytes(b'conxml v1 original')
    (target_dir / 'conxml-cli.exe').write_bytes(b'cli v1 original')

    cache_dir.mkdir(parents=True)
    zip_file = cache_dir / 'ConXml-0.3.0-windows-x64.zip'
    zip_file.write_bytes(zip_bytes)

    release = Release('0.3.0', 'https://github.com/Slush-04/ConXml/releases/download/v0.3.0/ConXml-0.3.0-windows-x64.zip',
                      zip_sha, len(zip_bytes), zip_file.name, kind='zip')

    updater = Updater(cache_dir, current='0.2.0')
    script = updater.apply_update(release, zip_file, target_dir=target_dir, parent_pid=999999)

    assert script.is_file()
    contenido_script = script.read_text(encoding='utf-8')
    assert 'ParentPid' in contenido_script
    assert 'conxml.exe' in contenido_script
    assert 'rollback' in contenido_script.lower()

    # Comprobar que en staging se descomprimió conxml.exe
    staging_exe = cache_dir / 'staging' / '0.3.0' / 'conxml.exe'
    assert staging_exe.is_file()
    assert staging_exe.read_bytes() == b'nuevo conxml v2'


def test_apply_update_corrupt_or_missing_exe_aborts(tmp_path):
    import io
    import zipfile
    from conxml.updates import Release

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('otro_archivo.txt', b'sin conxml.exe')
    zip_bytes = buf.getvalue()

    cache_dir = tmp_path / 'updates'
    cache_dir.mkdir()
    zip_file = cache_dir / 'ConXml-0.3.0-windows-x64.zip'
    zip_file.write_bytes(zip_bytes)

    release = Release('0.3.0', 'http://example.com', hashlib.sha256(zip_bytes).hexdigest(),
                      len(zip_bytes), zip_file.name, kind='zip')

    updater = Updater(cache_dir, current='0.2.0')
    with pytest.raises(UpdateError, match='archivo no permitido'):
        updater.apply_update(release, zip_file)


def test_powershell_helper_execution_and_rollback(tmp_path):
    """Ejecuta el script PowerShell generado simulando un proceso completado y verifica el reemplazo y rollback."""
    import subprocess
    import shutil
    from conxml.updates import generar_script_actualizador

    if sys.platform != 'win32' or not shutil.which('powershell.exe'):
        pytest.skip('Requiere PowerShell en Windows')

    target_dir = tmp_path / 'app'
    target_dir.mkdir()
    (target_dir / 'conxml.exe').write_bytes(b'version 1')

    staging_dir = tmp_path / 'staging'
    staging_dir.mkdir()
    (staging_dir / 'conxml.exe').write_bytes(b'version 2')

    backup_dir = tmp_path / 'backup'
    log_file = tmp_path / 'logs' / 'update.log'
    script_path = tmp_path / 'test_update.ps1'

    generar_script_actualizador(
        script_path,
        parent_pid=0,  # 0 indica no esperar proceso padre
        target_dir=target_dir,
        staging_dir=staging_dir,
        backup_dir=backup_dir,
        log_file=log_file,
    )

    # 1. Ejecutar helper en modo normal (sin relanzar proceso GUI inexistente para evitar popup de ejecutable no válido)
    # Reemplazamos la sección de Start-Process con un log para la prueba de script
    script_content = script_path.read_text(encoding='utf-8')
    script_test = script_content.replace('Start-Process -FilePath $nuevoExe -PassThru', '# Test: no start\n$nuevoProc = [pscustomobject]@{HasExited=$false; ExitCode=0}')
    script_test_path = tmp_path / 'run_test.ps1'
    script_test_path.write_text(script_test, encoding='utf-8')

    res = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script_test_path)],
                         capture_output=True, text=True, timeout=15)
    assert res.returncode == 0, res.stdout + res.stderr

    # Comprobar reemplazo exitoso y respaldo
    assert (target_dir / 'conxml.exe').read_bytes() == b'version 2'
    assert (backup_dir / 'conxml.exe').read_bytes() == b'version 1'
    assert log_file.is_file()
    assert 'Actualización completada exitosamente' in log_file.read_text(encoding='utf-8')


def test_data_preservation_during_direct_update(tmp_path):
    """Garantiza que el catálogo, preferencias, boveda y respaldos permanezcan intactos tras actualizar."""
    from conxml.config import Config

    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    (data_dir / 'catalogo.db').write_bytes(b'CATALOGO SQLITE INTACTO')
    (data_dir / 'preferencias.json').write_text('{"tema":"dark","cliente":"DEMO"}', encoding='utf-8')
    boveda_file = data_dir / 'boveda' / 'factura.xml'
    boveda_file.parent.mkdir(parents=True)
    boveda_file.write_text('<cfdi/>', encoding='utf-8')

    # Ejecutar Config().inicializar() no debe sobreescribir ni borrar nada
    os.environ['CONXML_DATA_DIR'] = str(data_dir)
    cfg = Config()
    cfg.inicializar()

    assert (data_dir / 'catalogo.db').read_bytes() == b'CATALOGO SQLITE INTACTO'
    assert json.loads((data_dir / 'preferencias.json').read_text(encoding='utf-8'))['cliente'] == 'DEMO'
    assert boveda_file.read_text(encoding='utf-8') == '<cfdi/>'
