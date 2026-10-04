"""Sincroniza versión Python, paquete y bundle; --check no modifica archivos."""
import argparse
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('version', nargs='?')
p.add_argument('--check', action='store_true')
a = p.parse_args()
init = root / 'src/conxml/__init__.py'
current = re.search(r'__version__ = "([^"]+)"', init.read_text()).group(1)
version = a.version or current
if not re.fullmatch(r'\d+\.\d+\.\d+', version):
    p.error('Usa X.Y.Z estable')
if any(int(n) > 65535 for n in version.split('.')):
    p.error('Los componentes de versión Windows deben ser menores de 65536')
for path, pattern in [(init, r'(__version__ = ")[^"]+'),
                      (root / 'pyproject.toml', r'(version = ")[^"]+'),
                      (root / 'conxml.spec', r'("CFBundle(?:ShortVersionString|Version)": ")[^"]+')]:
    content = path.read_text()
    values = [m.group(0).split('"')[-1] for m in re.finditer(pattern, content)]
    if a.check:
        if any(v != version for v in values):
            raise SystemExit(f'Versión inconsistente en {path}')
    else:
        # Sustituye solo el número; conserva comillas y resto del archivo.
        path.write_text(re.sub(pattern, lambda m: m.group(1) + version, content))
print(version)
