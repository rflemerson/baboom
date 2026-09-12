"""Tests for admin API error classification and session persistence."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from mcp_server.tools.admin_api import (
    AdminAPIClient,
    AuthenticationError,
    NetworkError,
    PermissionDeniedError,
    ValidationError,
)


def response(status: int, body: dict, cookies: dict[str, str] | None = None) -> Mock:
    """Build a requests response double."""
    result = Mock()
    result.status_code = status
    result.json.return_value = body
    result.cookies = requests.cookies.cookiejar_from_dict(cookies or {})
    return result


def test_failed_login_returns_clear_error(tmp_path: Path) -> None:
    """Turn a rejected login into a clear authentication error."""
    client = AdminAPIClient("http://example.test", tmp_path / "session.json")
    client.session.get = Mock(return_value=response(200, {}, {"csrftoken": "token"}))
    client.session.request = Mock(
        return_value=response(
            403,
            {"error": {"code": "invalid_credentials", "message": "Rejected"}},
        ),
    )

    with pytest.raises(AuthenticationError, match="invalid credentials"):
        client.login("operator", "wrong")


def test_validation_error_preserves_field_errors(tmp_path: Path) -> None:
    """Expose ModelForm field errors without duplicating validation."""
    client = AdminAPIClient("http://example.test", tmp_path / "session.json")
    client.session.request = Mock(
        return_value=response(
            400,
            {
                "error": {
                    "code": "validation_failed",
                    "message": "Invalid fields",
                    "fields": {"name": ["This field is required."]},
                },
            },
        ),
    )

    with pytest.raises(ValidationError) as raised:
        client.create("core", "product", {})

    assert raised.value.fields == {"name": ["This field is required."]}


def test_permission_error_is_distinct_from_network_error(tmp_path: Path) -> None:
    """Distinguish a Django permission response from transport failure."""
    client = AdminAPIClient("http://example.test", tmp_path / "session.json")
    client.session.request = Mock(
        return_value=response(
            403,
            {"error": {"code": "forbidden", "message": "Permission denied."}},
        ),
    )
    with pytest.raises(PermissionDeniedError):
        client.registry()

    client.session.request = Mock(side_effect=requests.ConnectionError("offline"))
    with pytest.raises(NetworkError):
        client.registry()


def test_session_cookie_is_persisted(tmp_path: Path) -> None:
    """Persist the session cookie jar after a successful request."""
    path = tmp_path / "session.json"
    client = AdminAPIClient("http://example.test", path)
    client.session.cookies.set("sessionid", "abc")
    client.persist_session()
    assert json.loads(path.read_text()) == {"cookies": {"sessionid": "abc"}}
