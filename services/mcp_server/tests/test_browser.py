"""Unit tests for browser safety boundaries and bounded returns."""

import asyncio

import pytest

from mcp_server.tools.browser import (
    BrowserError,
    BrowserManager,
    _assert_read_only_expression,
    _truncate,
    is_allowed_url,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://growth.example/products/1", "allow"),
        ("https://cdn.growth.example/image.png", "allow"),
        ("http://localhost:8000/", "deny"),
        ("http://127.0.0.1/", "deny"),
        ("http://127.42.0.1/", "deny"),
        ("http://10.0.0.4/", "deny"),
        ("http://172.16.0.4/", "deny"),
        ("http://192.168.1.4/", "deny"),
        ("http://169.254.169.254/latest/meta-data/", "deny"),
        ("http://[::1]/", "deny"),
        ("file:///etc/passwd", "deny"),
    ],
)
def test_url_allowlist_blocks_unsafe_addresses(url: str, expected: str) -> None:
    """Accept the registered domain and reject local or private targets."""
    result, _reason = is_allowed_url(url, "growth.example")
    assert result is (expected == "allow")


def test_redirect_outside_registered_domain_is_rejected() -> None:
    """Apply the same allowlist to a URL supplied as a redirect target."""
    allowed, reason = is_allowed_url(
        "https://attacker.example/redirect",
        "growth.example",
    )

    assert allowed is False
    assert "registered domain" in reason


def test_html_requires_a_selector_before_page_access() -> None:
    """Guide callers to snapshot refs instead of returning a whole page."""
    with pytest.raises(BrowserError, match="selector is required"):
        # The empty selector is rejected before requiring a live browser page.
        asyncio.run(BrowserManager().html(""))


def test_truncation_reports_original_size_and_remaining() -> None:
    """Bounded returns tell the caller exactly how much content was omitted."""
    result = _truncate("abcdefghij", 4)

    assert result == {
        "text": "abcd",
        "truncated": True,
        "originalLength": 10,
        "remaining": 6,
        "warning": "Response truncated; 6 characters omitted.",
    }


def test_evaluate_rejects_mutation() -> None:
    """Read-only evaluation cannot invoke navigation, storage, or assignment."""
    with pytest.raises(BrowserError, match="read-only"):
        _assert_read_only_expression("document.body.innerHTML = 'changed'")


def test_evaluate_allows_reading_location() -> None:
    """Reading the current URL remains available to evidence inspection."""
    _assert_read_only_expression("window.location.href")
