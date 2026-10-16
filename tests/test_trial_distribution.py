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
