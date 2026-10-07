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
    controller = Actualizaciones.__new__(Actualizaciones)
    controller.updater = SimpleNamespace(demo='', launch=lambda *a: events.append('instalador'))
    controller.app = SimpleNamespace(guardar_sesion=lambda: events.append('sesion'),
                                     ejecutar=lambda fn, cb, *a: cb(fn()),
                                     master=SimpleNamespace(destroy=lambda: events.append('cerrar')))
    controller._downloaded(SimpleNamespace(), tmp_path / 'setup.exe')
    assert events == ['sesion', 'respaldo', 'instalador', 'cerrar']
