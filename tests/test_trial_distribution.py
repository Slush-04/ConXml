import base64
import json
from pathlib import Path
import runpy

import pytest


def test_distribution_contains_only_public_configuration(tmp_path):
    generate = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/trial_distribution.py'))['generate']
    policy = tmp_path / 'policy.json'
    destination = tmp_path / 'distribucion.py'
    policy.write_text(json.dumps({'service_url': 'https://licenses.example', 'trusted_keys': {'key-1': base64.urlsafe_b64encode(b'p' * 32).decode().rstrip('=')}}))
    generate(policy, destination)
    config = runpy.run_path(str(destination))
    assert config['MODE'] == 'trial'
    assert config['TRUSTED_KEYS'] == {'key-1': b'p' * 32}
    policy.write_text(json.dumps({'service_url': 'http://localhost', 'trusted_keys': {}}))
    with pytest.raises(ValueError):
        generate(policy, destination)


def test_pyinstaller_archive_uses_trial_policy_instead_of_cached_development(tmp_path):
    """Ejercita el PYZ real con el caché de código que mantiene PyInstaller."""
    import subprocess
    import sys
    pytest.importorskip('PyInstaller')
    helper = Path(__file__).resolve().parents[1] / 'scripts/trial_distribution.py'
    source = tmp_path / 'development.py'
    source.write_text("MODE = 'development'\nSERVICE_URL = ''\nTRUSTED_KEYS = {}\n")
    public = tmp_path / 'public.json'
    public.write_text(json.dumps({'service_url': 'https://licenses.example', 'trusted_keys': {
        'key-1': base64.urlsafe_b64encode(b'p' * 32).decode().rstrip('=')}}))
    policy = tmp_path / 'trial.py'
    spec = tmp_path / 'policy.spec'
    spec.write_text(f'''
import runpy
from types import SimpleNamespace
from PyInstaller.config import CONF
helper = runpy.run_path({str(helper)!r})
policy = helper['generate']({str(public)!r}, {str(policy)!r})
for index in range(2):
    original = [('conxml.distribucion', {str(source)!r}, 'PYMODULE')]
    CONF['code_cache'][id(original)] = {{'conxml.distribucion': compile("MODE = 'development'", {str(source)!r}, 'exec')}}
    analysis = SimpleNamespace(pure=original)
    helper['embed_policy'](analysis, policy)
    assert analysis.pure is original
    archive = PYZ(analysis.pure)
    helper['verify_archive'](archive.name, policy)
print('GUI and CLI: trial policy verified in actual PYZ archives.')
''')
    result = subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                             '--workpath', str(tmp_path / 'work'), '--distpath', str(tmp_path / 'dist'),
                             str(spec)], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'trial policy verified' in result.stdout
