"""Contrato independiente; no activa licencias ni toca la configuración del usuario."""
import base64
import json
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from conxml.licencias import LicenseError, verify_lease


def encode(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@pytest.fixture
def contract():
    private = Ed25519PrivateKey.generate()
    payload = {"schema": 1, "iss": "conxml-licensing", "aud": "conxml", "license_id": str(uuid4()),
               "device_id": str(uuid4()), "iat": 1800000000, "exp": 1800086400,
               "trial_expires_at": 1801296000, "status": "trial", "license_revision": 2,
               "device_revision": 3, "nonce": str(uuid4())}

    def sign(changes=None, header=None):
        head = {"alg": "EdDSA", "typ": "JWT", "kid": "test-1", **(header or {})}
        content = encode(json.dumps(head).encode()) + "." + encode(json.dumps({**payload, **(changes or {})}).encode())
        return content + "." + encode(private.sign(content.encode()))

    def verify(token, **overrides):
        return verify_lease(token, {"test-1": private.public_key().public_bytes_raw()},
                            **{"device_id": payload["device_id"], "expected_nonce": payload["nonce"], **overrides})

    return payload, sign, verify


def test_valid_signature_and_exact_expiration_boundary(contract):
    payload, sign, verify = contract
    lease = verify(sign())
    assert lease.permits_use(payload["iat"])
    assert lease.permits_use(payload["exp"] - 1)
    assert not lease.permits_use(payload["exp"])
    assert not lease.permits_use(payload["iat"] - 1)


@pytest.mark.parametrize("status", ["blocked", "revoked", "expired"])
def test_signed_denial_never_grants_use(contract, status):
    payload, sign, verify = contract
    lease = verify(sign({"status": status, "exp": payload["iat"]}))
    assert lease.status == status
    assert not lease.permits_use(payload["iat"])


def test_other_installation_nonce_and_old_revisions_are_rejected(contract):
    _, sign, verify = contract
    for overrides in [{"device_id": str(uuid4())}, {"expected_nonce": str(uuid4())},
                      {"minimum_license_revision": 3}, {"minimum_device_revision": 4}]:
        with pytest.raises(LicenseError):
            verify(sign(), **overrides)


@pytest.mark.parametrize("changes", [
    {"aud": "another-product"}, {"iss": "other-service"}, {"schema": True},
    {"exp": 1800086401}, {"trial_expires_at": 1800000100}, {"status": "unlimited"},
    {"iat": True}, {"license_revision": -1}, {"device_revision": 1.5},
    {"device_id": "invalid"}, {"extra": "field"},
])
def test_claims_rejected_even_with_a_valid_signature(contract, changes):
    _, sign, verify = contract
    with pytest.raises(LicenseError):
        verify(sign(changes))


@pytest.mark.parametrize("header", [{"alg": "none"}, {"alg": "HS256"}, {"kid": "unknown"},
                                   {"jku": "https://untrusted.example/keys"}])
def test_caller_cannot_select_an_algorithm_or_download_other_keys(contract, header):
    _, sign, verify = contract
    with pytest.raises(LicenseError):
        verify(sign(header=header))


def test_altered_signature_and_malformed_compact_tokens_are_rejected(contract):
    _, sign, verify = contract
    token = sign()
    head, payload, signature = token.split(".")
    changed = ("A" if signature[0] != "A" else "B") + signature[1:]
    for invalid in [f"{head}.{payload}.{changed}", token + "=", token + ".part", "", "x" * 8193, None]:
        with pytest.raises(LicenseError):
            verify(invalid)
