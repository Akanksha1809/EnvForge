import hashlib
import hmac

from app.core.config import get_settings
from app.services.webhooks import verify_signature


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_is_accepted() -> None:
    secret = get_settings().github_webhook_secret
    body = b'{"hello": "world"}'
    assert verify_signature(body, _sign(secret, body)) is True


def test_wrong_secret_is_rejected() -> None:
    body = b'{"hello": "world"}'
    assert verify_signature(body, _sign("wrong-secret", body)) is False


def test_tampered_body_is_rejected() -> None:
    secret = get_settings().github_webhook_secret
    signature = _sign(secret, b'{"hello": "world"}')
    assert verify_signature(b'{"hello": "tampered"}', signature) is False


def test_missing_signature_header_is_rejected() -> None:
    assert verify_signature(b"{}", None) is False


def test_malformed_signature_header_is_rejected() -> None:
    assert verify_signature(b"{}", "not-a-real-signature") is False
