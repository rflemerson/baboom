"""Django test runner that keeps the suite off the public network."""

from __future__ import annotations

import ipaddress
import socket
from contextlib import ExitStack
from importlib import import_module
from typing import TYPE_CHECKING
from unittest.mock import patch

from django.db import connections
from django.test.runner import DiscoverRunner

if TYPE_CHECKING:
    from collections.abc import Callable


LOOPBACK_NAMES = frozenset({"localhost", "ip6-localhost"})
MIN_NETWORK_ADDRESS_PARTS = 2


class ExternalNetworkAccessError(RuntimeError):
    """A test attempted to open a socket outside the test environment."""


class NoNetworkTestRunner(DiscoverRunner):
    """Discover and run tests with external socket access disabled."""

    def run_suite(self, suite: object, **kwargs: object) -> object:
        """Run the suite while permitting only local and test-DB sockets."""
        allowed_hosts = self._database_hosts()
        curl = import_module("curl_cffi")
        with ExitStack() as stack:
            connect = socket.socket.connect
            connect_ex = socket.socket.connect_ex
            # Curl.perform is the synchronous path. AsyncSession, which
            # scrapy-impersonate downloads through, never calls it: it hands the
            # handle to the multi interface through AsyncCurl.add_handle.
            stack.enter_context(
                patch.object(
                    curl.Curl,
                    "perform",
                    new=self._guard_curl(curl.CurlInfo),
                ),
            )
            stack.enter_context(
                patch.object(
                    import_module("curl_cffi.aio").AsyncCurl,
                    "add_handle",
                    new=self._guard_async_curl(curl.CurlInfo),
                ),
            )
            stack.enter_context(
                patch.object(
                    socket.socket,
                    "connect",
                    new=self._guard(connect, allowed_hosts),
                ),
            )
            stack.enter_context(
                patch.object(
                    socket.socket,
                    "connect_ex",
                    new=self._guard(connect_ex, allowed_hosts),
                ),
            )
            return super().run_suite(suite, **kwargs)

    @staticmethod
    def _guard_curl(curl_info: object) -> Callable[..., object]:
        """Reject every libcurl transfer before it reaches native code."""

        def guarded(curl: object, *_args: object, **_kwargs: object) -> None:
            destination = curl.getinfo(curl_info.EFFECTIVE_URL)
            if isinstance(destination, bytes):
                destination = destination.decode("utf-8", errors="replace")
            message = (
                f"External curl_cffi request blocked: {destination or '<unknown>'}"
            )
            raise ExternalNetworkAccessError(message)

        return guarded

    @staticmethod
    def _guard_async_curl(curl_info: object) -> Callable[..., object]:
        """Reject a libcurl handle before the multi interface starts it."""
        reject = NoNetworkTestRunner._guard_curl(curl_info)

        def guarded(_multi: object, curl: object, *_args: object) -> None:
            reject(curl)

        return guarded

    def _database_hosts(self) -> frozenset[str]:
        """Return configured hosts used by the test databases."""
        hosts = set(LOOPBACK_NAMES)
        for connection in connections.all():
            settings = connection.settings_dict
            host = settings.get("HOST") or settings.get("TEST", {}).get("HOST")
            if host:
                hosts.add(str(host).casefold())
        return frozenset(hosts)

    @staticmethod
    def _guard(
        original: Callable[..., object],
        allowed_hosts: frozenset[str],
    ) -> Callable[..., object]:
        """Build a socket method that rejects destinations outside the suite."""

        def guarded(socket_object: object, address: object) -> object:
            host = NoNetworkTestRunner._address_host(address)
            if not NoNetworkTestRunner._host_is_allowed(host, allowed_hosts):
                destination = NoNetworkTestRunner._destination(address)
                message = f"External socket connection blocked: {destination}"
                raise ExternalNetworkAccessError(message)
            return original(socket_object, address)

        return guarded

    @staticmethod
    def _address_host(address: object) -> str:
        """Extract a host from an IPv4/IPv6 or Unix socket address."""
        host = address[0] if isinstance(address, tuple) and address else address
        if isinstance(host, bytes):
            return host.decode("latin-1").casefold()
        return str(host).casefold()

    @staticmethod
    def _destination(address: object) -> str:
        """Format the attempted socket destination for the failure message."""
        if isinstance(address, tuple) and len(address) >= MIN_NETWORK_ADDRESS_PARTS:
            host, port = address[0], address[1]
            return f"[{host}]:{port}" if ":" in str(host) else f"{host}:{port}"
        return str(address)

    @staticmethod
    def _host_is_allowed(host: str, allowed_hosts: frozenset[str]) -> bool:
        """Allow loopback IPs and explicitly configured database hosts."""
        if host in allowed_hosts:
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False
