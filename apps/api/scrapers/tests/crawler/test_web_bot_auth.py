"""Web Bot Auth: keys, signatures and the self-identifying Shopify spider."""

from __future__ import annotations

import base64
import json
from http import HTTPStatus
from typing import TYPE_CHECKING

from django.test import Client, SimpleTestCase, override_settings
from scrapy import Request

from scrapers.crawler.middlewares import ImpersonationMiddleware
from scrapers.crawler.web_bot_auth import (
    AGENT,
    DIRECTORY_CONTENT_TYPE,
    DIRECTORY_PATH,
    USER_AGENT,
    authority,
    load_private_key,
    public_jwk,
    request_headers,
    thumbprint,
)
from scrapers.stores.growth import GrowthSpider
from scrapers.stores.soldiers import SoldiersSpider

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

NOW = 1_791_600_000
# SYNTHETIC test key, never used outside this module.
SEED = "nWGxne_9WmC6hEr0kuwsxERJxWl7MmkZcDusAxyuf2A"
KEY = load_private_key(SEED)


def _verify(key: Ed25519PrivateKey, headers: dict[str, str], lines: list[str]) -> None:
    params = headers["Signature-Input"].removeprefix("sig1=")
    base = "\n".join([*lines, f'"@signature-params": {params}']).encode()
    raw = headers["Signature"].removeprefix("sig1=:").removesuffix(":")
    key.public_key().verify(base64.b64decode(raw), base)


class SignatureTests(SimpleTestCase):
    """Keys are named by their RFC 7638 thumbprint; signatures verify."""

    def test_the_thumbprint_matches_rfc_8037(self) -> None:
        """RFC 8037, appendix A.3."""
        jwk = {
            "kty": "OKP",
            "crv": "Ed25519",
            "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
        }

        assert thumbprint(jwk) == "kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k"

    def test_authority_drops_only_the_default_port(self) -> None:
        """Host in lower case; a non-default port stays."""
        assert authority("https://Shop.Example/products.json?page=2") == "shop.example"
        assert authority("https://shop.example:8443/x") == "shop.example:8443"

    def test_a_request_signs_its_authority_and_agent(self) -> None:
        """The signature base is rebuilt as a verifier would."""
        headers = request_headers(KEY, "https://store.example/collections.json", NOW)
        params = headers["Signature-Input"]

        assert headers["Signature-Agent"] == f'"{AGENT}"'
        assert params.startswith('sig1=("@authority" "signature-agent");')
        assert f"created={NOW};expires={NOW + 60}" in params
        assert f'keyid="{thumbprint(public_jwk(KEY))}"' in params
        assert 'tag="web-bot-auth"' in params
        _verify(
            KEY,
            headers,
            ['"@authority": store.example', f'"signature-agent": "{AGENT}"'],
        )


@override_settings(WEB_BOT_AUTH_PRIVATE_KEY=SEED)
class IdentityTests(SimpleTestCase):
    """Shopify spiders say who they are; the others keep their old client."""

    def test_a_shopify_spider_signs_and_never_impersonates(self) -> None:
        """Its own User-Agent, robots.txt obeyed, every request signed."""
        request = Request("https://soldiersnutrition.com.br/collections.json")

        ImpersonationMiddleware().process_request(request, SoldiersSpider())

        assert "impersonate" not in request.meta
        assert request.headers.get("Signature")
        assert SoldiersSpider.custom_settings == {
            "ROBOTSTXT_OBEY": True,
            "USER_AGENT": USER_AGENT,
        }

    def test_another_platform_keeps_its_browser_identity(self) -> None:
        """Only spiders that identify themselves change."""
        request = Request("https://www.gsuplementos.com.br/")

        ImpersonationMiddleware().process_request(request, GrowthSpider())

        assert request.meta["impersonate"]
        assert not request.headers.get("Signature")

    @override_settings(WEB_BOT_AUTH_PRIVATE_KEY="")
    def test_without_a_key_nothing_is_signed(self) -> None:
        """The spider still identifies itself."""
        request = Request("https://soldiersnutrition.com.br/collections.json")

        ImpersonationMiddleware().process_request(request, SoldiersSpider())

        assert "impersonate" not in request.meta
        assert not request.headers.get("Signature")


@override_settings(WEB_BOT_AUTH_PRIVATE_KEY=SEED)
class DirectoryTests(SimpleTestCase):
    """The origin publishes the public key, signed for its own host."""

    def test_the_directory_publishes_the_key_and_signs_itself(self) -> None:
        """A verifier finds the key by thumbprint and checks the response."""
        response = Client().get(DIRECTORY_PATH, HTTP_HOST="baboom.com.br")

        assert response.status_code == HTTPStatus.OK
        assert response["Content-Type"] == DIRECTORY_CONTENT_TYPE
        assert json.loads(response.content) == {"keys": [public_jwk(KEY)]}
        assert 'tag="http-message-signatures-directory"' in response["Signature-Input"]
        _verify(KEY, dict(response.items()), ['"@authority";req: baboom.com.br'])

    @override_settings(WEB_BOT_AUTH_PRIVATE_KEY="")
    def test_without_a_key_there_is_no_directory(self) -> None:
        """Nothing is published when nothing is signed."""
        assert Client().get(DIRECTORY_PATH).status_code == HTTPStatus.NOT_FOUND
