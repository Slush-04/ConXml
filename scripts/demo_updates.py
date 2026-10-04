"""Servidor local para probar aviso/descarga sin ejecutar binarios Windows.

CONXML_UPDATE_DEMO_URL=http://127.0.0.1:8765/latest
CONXML_DATA_DIR=/tmp/conxml-demo PYTHONPATH=src .venv/bin/python -m conxml.ui_main
"""
import argparse
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

p = argparse.ArgumentParser()
p.add_argument('--port', type=int, default=8765)
p.add_argument('--mode', choices=['update', 'current', 'missing', 'corrupt', 'truncated', 'draft', 'incompatible', 'offline'], default='update')
a = p.parse_args()
payload = b'ConXml DEMO - no es un ejecutable Windows\n' * 4096
version = '0.2.99999' if a.mode != 'current' else '0.2.0'
name = f'ConXml-Setup-{version}-windows-x64.exe'
if a.mode == 'incompatible':
    name = name.replace('x64', 'arm64')
asset = {'name': name, 'state': 'uploaded', 'size': len(payload),
         'digest': 'sha256:' + hashlib.sha256(payload).hexdigest(),
         'browser_download_url': f'http://127.0.0.1:{a.port}/{name}'}
release = {'tag_name': f'v{version}', 'draft': a.mode == 'draft', 'prerelease': False,
           'assets': [] if a.mode == 'missing' else [asset]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if a.mode == 'offline':
            self.send_error(503)
            return
        if self.path == '/latest':
            body = json.dumps(release).encode()
        elif self.path == '/' + name:
            body = (b'X' + payload[1:]) if a.mode == 'corrupt' else payload
            if a.mode == 'truncated':
                body = body[:1024]
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


print(f'Demo {a.mode}: http://127.0.0.1:{a.port}/latest', flush=True)
ThreadingHTTPServer(('127.0.0.1', a.port), Handler).serve_forever()
