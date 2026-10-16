"""Pruebas de integración del cliente sin keyring, red ni datos reales."""
import base64
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from conxml import licensing_client as lc
from conxml.licencias import LicenseError


class Vault:
    value = None
    fail = False

    def get_password(self, *args):
        return self.value

    def set_password(self, *args):
        if self.fail:
            raise RuntimeError('secret')
        self.value = args[-1]


def encode(data):
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


@pytest.fixture
def setup(tmp_path, monkeypatch):
    private = Ed25519PrivateKey.generate()
    clock = SimpleNamespace(wall=1800000000., mono=0.)
    vault = Vault()
    clients = []
    state = {'status': 'trial', 'revision': 0, 'license': str(uuid4()), 'nonce': None}
    calls = []

    def response(url, path, payload, token=None):
        calls.append((path, payload.copy(), token))
        assert vault.value is not None  # La identidad se guarda antes del envío.
        now = int(clock.wall)
        claims = {'schema': 1, 'iss': 'conxml-licensing', 'aud': 'conxml',
                  'device_id': payload['device_id'], 'license_id': state['license'],
                  'iat': now, 'exp': now + 600 if state['status'] == 'trial' else now,
                  'trial_expires_at': now + 600, 'status': state['status'],
                  'license_revision': state['revision'], 'device_revision': 0,
                  'nonce': state['nonce'] or payload['nonce']}
        text = encode(json.dumps({'alg': 'EdDSA', 'typ': 'JWT', 'kid': 'test'}).encode()) + '.' + encode(json.dumps(claims).encode())
        return {'schema': 1, 'server_time': now, 'lease': text + '.' + encode(private.sign(text.encode()))}
    monkeypatch.setattr(lc, 'request_json', response)

    def create():
        client = lc.LicenseClient(mode='trial', url='https://licenses.example',
                                  keys={'test': private.public_key().public_bytes_raw()},
                                  directory=tmp_path, vault=vault, wall=lambda: clock.wall,
                                  monotonic=lambda: clock.mono)
        clients.append(client)
        return client
    yield create, clock, vault, state, calls
    for client in clients:
        client.close()


def test_first_activation_then_exact_expiration(setup):
    create, clock, vault, state, calls = setup
    client = create()
    assert not client.allowed()
    client.sync('a' * 43)
    assert client.allowed()
    assert 'a' * 43 not in vault.value
    clock.mono = 600
    assert not client.allowed()


def test_network_never_grants_permission_and_retry_preserves_identity(setup, monkeypatch):
    create, clock, vault, state, calls = setup
    client = create()
    original = lc.request_json
    def fail(*args, **kwargs):
        raise LicenseError('Sin conexión')
    monkeypatch.setattr(lc, 'request_json', fail)
    identity = client.record['device_id'], client.record['token']
    with pytest.raises(LicenseError):
        client.sync('a' * 43)
    assert not client.allowed()
    clock.mono = client.next_attempt
    monkeypatch.setattr(lc, 'request_json', original)
    client.sync('a' * 43)
    assert identity == (client.record['device_id'], client.record['token'])


def test_denial_survives_restart_and_old_revision(setup):
    create, clock, vault, state, calls = setup
    client = create()
    client.sync('a' * 43)
    old = client.record['lease']
    state.update(status='blocked', revision=1)
    clock.mono = client.next_attempt
    client.sync()
    assert not client.allowed()
    # Alterar la copia JSON no restaura un permiso positivo.
    (client.directory / 'lease.json').write_text(json.dumps({'lease': old}))
    client.close()
    client = create()
    assert not client.allowed()
    state.update(status='trial', revision=0)
    with pytest.raises(LicenseError):
        client.sync()
    assert not client.allowed()


def test_signed_unblock_requires_new_revision(setup):
    create, clock, vault, state, calls = setup
    state.update(status='blocked', revision=1)
    client = create()
    client.sync('a' * 43)
    assert not client.allowed()
    state.update(status='trial', revision=2)
    clock.mono = client.next_attempt
    client.sync()
    assert client.allowed()


def test_wrong_nonce_is_rejected_before_persistence(setup):
    create, clock, vault, state, calls = setup
    client = create()
    previous = vault.value
    state['nonce'] = str(uuid4())
    with pytest.raises(LicenseError):
        client.sync('a' * 43)
    assert vault.value == previous
    assert not client.allowed()


def test_clock_rollback_requires_online_validation(setup):
    create, clock, vault, state, calls = setup
    client = create()
    client.sync('a' * 43)
    clock.mono += 100
    clock.wall += 100
    assert client.allowed()
    client.close()
    clock.wall -= 100
    client = create()
    assert not client.allowed()
    clock.wall += 100
    client.sync()
    assert client.allowed()


def test_monotonic_expiration_with_frozen_wall(setup):
    create, clock, vault, state, calls = setup
    client = create()
    client.sync('a' * 43)
    clock.mono += 601
    assert not client.allowed()


def test_short_restarts_consume_offline_time(setup):
    create, clock, vault, state, calls = setup
    client = create()
    client.sync('a' * 43)
    for _ in range(21):
        client.allowed()
        client.close()
        client = create()
    assert not client.allowed()


def test_future_clock_does_not_extend_permission(setup):
    create, clock, vault, state, calls = setup
    client = create()
    client.sync('a' * 43)
    clock.wall += 1000
    assert not client.allowed()


def test_vault_failure_closes_access(setup):
    create, clock, vault, state, calls = setup
    client = create()
    vault.fail = True
    with pytest.raises(LicenseError):
        client.sync('a' * 43)
    assert not client.allowed()


def test_single_session_and_corrupt_vault(setup):
    create, clock, vault, state, calls = setup
    client = create()
    with pytest.raises(LicenseError, match='ya está abierto'):
        create()
    client.close()
    vault.value = '{}'
    with pytest.raises(LicenseError, match='identidad'):
        create()


def test_development_is_exempt_without_vault_or_service():
    client = lc.LicenseClient(mode='development', vault=None)
    assert client.allowed()


def test_bad_trial_configuration_never_falls_back_to_development():
    with pytest.raises(LicenseError):
        lc.LicenseClient(mode='trial', url='', keys={})


def test_transport_blocks_redirects_and_limits_decompressed_body(monkeypatch):
    class Response:
        status_code = 200
        headers = {}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def iter_content(self, size):
            yield b'x' * (lc.MAX_RESPONSE + 1)
    response = Response()
    def request(*args, **kwargs):
        assert kwargs['allow_redirects'] is False
        assert kwargs['stream'] is True
        return response
    monkeypatch.setattr(lc.requests, 'request', request)
    # Restaurar el transporte real: esta prueba no usa setup.
    with pytest.raises(LicenseError):
        lc.request_json('https://test.invalid', '/v1/check-in', {})
    response.status_code = 302
    with pytest.raises(LicenseError):
        lc.request_json('https://test.invalid', '/v1/check-in', {})
    response.status_code = 429
    response.headers = {'Retry-After': '600'}
    with pytest.raises(lc.RetryLater) as exc:
        lc.request_json('https://test.invalid', '/v1/check-in', {})
    assert exc.value.seconds == 600


def test_failed_vault_write_does_not_lose_received_denial_after_restart(setup):
    create, clock, vault, state, calls = setup
    client = create()
    client.sync('a' * 43)
    state.update(status='blocked', revision=1)
    clock.mono = client.next_attempt
    vault.fail = True
    with pytest.raises(LicenseError):
        client.sync()
    assert not client.allowed()
    client.close()
    vault.fail = False
    client = create()
    assert not client.allowed()
    state.update(status='trial', revision=0)
    with pytest.raises(LicenseError):
        client.sync()
    assert not client.allowed()


@pytest.mark.parametrize('contents', ['broken', '{}', '{"lease": "broken"}'])
def test_corrupt_cache_requires_online_validation(setup, contents):
    create, clock, vault, state, calls = setup
    client = create()
    client.sync('a' * 43)
    (client.directory / 'lease.json').write_text(contents)
    client.close()
    client = create()
    assert not client.allowed()
    client.sync()
    assert client.allowed()


def test_journal_failure_stops_old_permit_in_current_session(setup, monkeypatch):
    create, clock, vault, state, calls = setup
    client = create()
    client.sync('a' * 43)
    assert client.allowed()
    state.update(status='blocked', revision=1)
    clock.mono = client.next_attempt
    def fail(*args):
        raise OSError('disk unavailable')
    monkeypatch.setattr(lc, 'save_record', fail)
    with pytest.raises(LicenseError):
        client.sync()
    assert not client.allowed()
