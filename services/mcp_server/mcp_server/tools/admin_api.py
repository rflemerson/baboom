"""Session based client for the Django admin REST API."""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from pathlib import Path
from typing import Any

import requests


class AdminAPIError(RuntimeError):
    """Base error raised by the admin API client."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        """Initialize the error with an optional HTTP status."""
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(AdminAPIError):
    """Raised when the admin login is rejected."""


class PermissionDeniedError(AdminAPIError):
    """Raised when Django denies an operation for the signed-in user."""


class ValidationError(AdminAPIError):
    """Raised when the admin ModelForm rejects submitted data."""

    def __init__(self, message: str, fields: dict[str, Any] | None = None) -> None:
        """Initialize the error with field-level validation details."""
        super().__init__(message, status_code=400)
        self.fields = fields or {}


class NetworkError(AdminAPIError):
    """Raised when the HTTP request cannot reach Django."""


class AdminAPIClient:
    """Small stateful HTTP client for the mounted admin REST API."""

    def __init__(
        self,
        base_url: str | None = None,
        session_path: str | Path | None = None,
    ) -> None:
        """Create a client and restore cookies from the session file."""
        configured_url = base_url or os.getenv("ADMIN_API_URL")
        if not configured_url:
            message = "ADMIN_API_URL is not configured."
            raise AdminAPIError(message)
        self.base_url = configured_url.rstrip("/")
        configured_path = session_path or os.getenv("ADMIN_API_SESSION_FILE")
        self.session_path = Path(
            configured_path or "~/.cache/baboom/admin-api-session.json",
        ).expanduser()
        self.session = requests.Session()
        self._restore_session()

    @staticmethod
    def _environment_credential(name: str) -> str:
        """Return a required credential without exposing its value."""
        value = os.getenv(name)
        if not value:
            message = f"{name} is not configured."
            raise AuthenticationError(message)
        return value

    def _restore_session(self) -> None:
        if not self.session_path.exists():
            return
        try:
            state = json.loads(self.session_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            message = "The persisted admin API session is invalid."
            raise AdminAPIError(message) from exc
        cookies = state.get("cookies") if isinstance(state, dict) else None
        if not isinstance(cookies, dict):
            message = "The persisted admin API session is invalid."
            raise AdminAPIError(message)
        for name, value in cookies.items():
            self.session.cookies.set(name, value)

    def persist_session(self) -> None:
        """Persist the current session cookies on disk."""
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"cookies": requests.utils.dict_from_cookiejar(self.session.cookies)}
        self.session_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self.session_path.chmod(0o600)

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            csrf = self.session.cookies.get("csrftoken")
            if csrf:
                headers["X-CSRFToken"] = csrf
        try:
            response = self.session.request(
                method,
                self._url(path),
                json=payload,
                params=params,
                headers=headers,
                timeout=60,
            )
        except requests.RequestException as exc:
            message = "Could not reach the Django admin API."
            raise NetworkError(message) from exc
        self.persist_session()
        body = self._decode_response(response)
        if retry_auth and self._is_session_expired(response.status_code, body):
            self.login()
            return self._request(
                method,
                path,
                payload=payload,
                params=params,
                retry_auth=False,
            )
        if response.status_code == HTTPStatus.FORBIDDEN:
            fallback = "Django denied this operation for the current user."
            raise PermissionDeniedError(
                self._error_message(body, fallback),
                status_code=HTTPStatus.FORBIDDEN,
            )
        if response.status_code == HTTPStatus.BAD_REQUEST:
            error = body.get("error", {})
            fallback = "The Django admin form rejected this data."
            raise ValidationError(
                self._error_message(body, fallback),
                fields=error.get("fields") if isinstance(error, dict) else None,
            )
        if response.status_code >= HTTPStatus.BAD_REQUEST:
            fallback = f"Django admin API returned HTTP {response.status_code}."
            raise AdminAPIError(
                self._error_message(body, fallback),
                status_code=response.status_code,
            )
        return body

    @staticmethod
    def _is_session_expired(status_code: int, body: dict[str, Any]) -> bool:
        """Identify an authentication response without swallowing permission 403s."""
        if status_code == HTTPStatus.UNAUTHORIZED:
            return True
        if status_code != HTTPStatus.FORBIDDEN:
            return False
        error = body.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        return code in {
            "session_expired",
            "not_authenticated",
            "authentication_required",
        }

    @staticmethod
    def _decode_response(response: requests.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            message = "Django returned an invalid JSON response."
            raise AdminAPIError(message) from exc
        if not isinstance(body, dict):
            message = "Django returned a non-object JSON response."
            raise AdminAPIError(message)
        return body

    @staticmethod
    def _error_message(body: dict[str, Any], fallback: str) -> str:
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if message:
                return str(message)
        return fallback

    def login(self) -> dict[str, Any]:
        """Authenticate through Django's session login endpoint and environment."""
        username = self._environment_credential("ADMIN_API_USERNAME")
        password = self._environment_credential("ADMIN_API_PASSWORD")
        try:
            self.session.get(self._url("admin/login/"), timeout=60)
        except requests.RequestException as exc:
            message = "Could not reach the Django admin API."
            raise NetworkError(message) from exc
        self.persist_session()
        try:
            body = self._request(
                "POST",
                "admin-api/api/v1/login/",
                payload={"username": username, "password": password},
                retry_auth=False,
            )
        except PermissionDeniedError as exc:
            message = (
                "Admin login failed: invalid credentials or insufficient permissions."
            )
            raise AuthenticationError(
                message,
                status_code=exc.status_code,
            ) from exc
        except NetworkError:
            raise
        except AdminAPIError as exc:
            if exc.status_code not in {
                HTTPStatus.BAD_REQUEST,
                HTTPStatus.UNAUTHORIZED,
                HTTPStatus.FORBIDDEN,
            }:
                raise
            message = (
                "Admin login failed: invalid credentials or insufficient permissions."
            )
            raise AuthenticationError(message, status_code=exc.status_code) from exc
        return body

    def registry(self) -> dict[str, Any]:
        """Discover the models visible to the signed-in user."""
        return self._request("GET", "admin-api/api/v1/registry/")

    def list(
        self,
        app_label: str,
        model_name: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        """List rows through the registered ModelAdmin queryset."""
        return self._request(
            "GET",
            f"admin-api/api/v1/{app_label}/{model_name}/",
            params=params,
        )

    def retrieve(
        self,
        app_label: str,
        model_name: str,
        pk: int | str,
    ) -> dict[str, Any]:
        """Retrieve one row through its registered ModelAdmin."""
        return self._request("GET", f"admin-api/api/v1/{app_label}/{model_name}/{pk}/")

    def create(
        self,
        app_label: str,
        model_name: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a row using the admin's real ModelForm."""
        return self._request(
            "POST",
            f"admin-api/api/v1/{app_label}/{model_name}/",
            payload=payload,
        )

    def update(
        self,
        app_label: str,
        model_name: str,
        pk: int | str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Patch a row using the admin's real ModelForm."""
        return self._request(
            "PATCH",
            f"admin-api/api/v1/{app_label}/{model_name}/{pk}/",
            payload=payload,
        )

    def autocomplete(
        self,
        app_label: str,
        model_name: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        """Resolve a foreign-key choice through the admin autocomplete view."""
        return self._request(
            "GET",
            f"admin-api/api/v1/{app_label}/{model_name}/autocomplete/",
            params=params,
        )

    def action(
        self,
        app_label: str,
        model_name: str,
        action_name: str,
        pks: list[int | str],
        *,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """Run a registered ModelAdmin action on selected primary keys."""
        return self._request(
            "POST",
            f"admin-api/api/v1/{app_label}/{model_name}/actions/{action_name}/",
            payload={"pks": pks, "confirmed": confirmed},
        )
