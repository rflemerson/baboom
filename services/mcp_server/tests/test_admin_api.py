"""Tests for admin API error classification and session persistence."""

import json
from typing import TYPE_CHECKING
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

if TYPE_CHECKING:
    from pathlib import Path

EXPECTED_RETRY_REQUESTS = 3


def response(status: int, body: dict, cookies: dict[str, str] | None = None) -> Mock:
    """Build a requests response double."""
    result = Mock()
    result.status_code = status
    result.json.return_value = body
    result.cookies = requests.cookies.cookiejar_from_dict(cookies or {})
    return result


def test_failed_login_returns_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Turn a rejected login into a clear authentication error."""
    client = AdminAPIClient("http://example.test", tmp_path / "session.json")
    monkeypatch.setenv("ADMIN_API_USERNAME", "operator")
    monkeypatch.setenv("ADMIN_API_PASSWORD", "wrong")
    client.session.get = Mock(return_value=response(200, {}, {"csrftoken": "token"}))
    client.session.request = Mock(
        return_value=response(
            403,
            {"error": {"code": "invalid_credentials", "message": "Rejected"}},
        ),
    )

    with pytest.raises(AuthenticationError, match="invalid credentials"):
        client.login()


def test_failed_login_http_401_is_authentication_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Classify an HTTP 401 from the login endpoint as bad credentials."""
    monkeypatch.setenv("ADMIN_API_USERNAME", "operator")
    monkeypatch.setenv("ADMIN_API_PASSWORD", "wrong")
    client = AdminAPIClient("http://example.test", tmp_path / "session.json")
    client.session.get = Mock(return_value=response(200, {}))
    client.session.request = Mock(return_value=response(401, {"error": {}}))

    with pytest.raises(AuthenticationError, match="invalid credentials"):
        client.login()


def test_missing_username_names_the_environment_variable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report the missing credential variable instead of a raw key error."""
    monkeypatch.delenv("ADMIN_API_USERNAME", raising=False)
    monkeypatch.setenv("ADMIN_API_PASSWORD", "secret")
    client = AdminAPIClient("http://example.test", tmp_path / "session.json")

    with pytest.raises(AuthenticationError, match="ADMIN_API_USERNAME"):
        client.login()


def test_expired_session_logs_in_and_retries_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refresh an expired session once, then repeat the original request."""
    monkeypatch.setenv("ADMIN_API_USERNAME", "operator")
    monkeypatch.setenv("ADMIN_API_PASSWORD", "secret")
    client = AdminAPIClient("http://example.test", tmp_path / "session.json")
    client.session.get = Mock(return_value=response(200, {}, {"csrftoken": "token"}))
    client.session.request = Mock(
        side_effect=[
            response(403, {"error": {"code": "session_expired", "message": "Expired"}}),
            response(200, {"user": {}}),
            response(200, {"results": []}),
        ],
    )

    assert client.registry() == {"results": []}
    assert client.session.request.call_count == EXPECTED_RETRY_REQUESTS


def test_password_is_never_written_to_session_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist cookies only, never the environment password."""
    credential = "super-secret-value"
    monkeypatch.setenv("ADMIN_API_USERNAME", "operator")
    monkeypatch.setenv("ADMIN_API_PASSWORD", credential)
    path = tmp_path / "session.json"
    client = AdminAPIClient("http://example.test", path)
    client.session.get = Mock(return_value=response(200, {}, {"csrftoken": "token"}))
    client.session.request = Mock(
        return_value=response(200, {"user": {}}, {"sessionid": "abc"}),
    )

    client.login()

    assert credential not in path.read_text()


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
