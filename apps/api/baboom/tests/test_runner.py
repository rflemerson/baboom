"""Tests for the project's no-network Django test runner."""

from __future__ import annotations

import socket
from importlib import import_module

from django.test import SimpleTestCase

from baboom.test_runner import ExternalNetworkAccessError

curl_requests = import_module("curl_cffi.requests")

EXTERNAL_SOCKET_HOST = "203.0.113.1"
EXTERNAL_SOCKET_PORT = 9
EXTERNAL_URL = "https://example.com"
CURL_TIMEOUT_SECONDS = 0.1


class NoNetworkTestRunnerTests(SimpleTestCase):
    """The configured runner rejects sockets aimed at public addresses."""

    def test_external_socket_is_rejected_with_its_destination(self) -> None:
        """An external socket fails with the blocked host and port in its message."""
        destination = f"{EXTERNAL_SOCKET_HOST}:{EXTERNAL_SOCKET_PORT}"
        raw_socket = socket.socket.__new__(socket.socket)
        try:
            socket.socket.connect(
                raw_socket,
                (EXTERNAL_SOCKET_HOST, EXTERNAL_SOCKET_PORT),
            )
        except ExternalNetworkAccessError as error:
            blocked_message = str(error)
        except OSError as error:
            raise AssertionError from error
        else:
            raise AssertionError

        assert destination in blocked_message

    def test_external_curl_request_is_rejected_with_its_destination(self) -> None:
        """A curl_cffi request fails before native code can reach the network."""
        try:
            curl_requests.get(EXTERNAL_URL, timeout=CURL_TIMEOUT_SECONDS)
        except ExternalNetworkAccessError as error:
            blocked_message = str(error)
        except (OSError, curl_requests.exceptions.RequestException) as error:
            raise AssertionError from error
        else:
            raise AssertionError

        assert EXTERNAL_URL in blocked_message
