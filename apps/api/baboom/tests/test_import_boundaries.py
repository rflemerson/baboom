"""The dependency rules of the pricing domain, checked on the source."""

from __future__ import annotations

import ast
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]


def _imports(package: str) -> dict[str, set[str]]:
    """Return the top-level packages each module of a package imports."""
    found: dict[str, set[str]] = {}
    for path in (ROOT / package).rglob("*.py"):
        if "migrations" in path.parts or "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names.add(node.module.split(".")[0])
        found[str(path.relative_to(ROOT))] = names
    return found


def _violations(package: str, forbidden: set[str]) -> list[str]:
    return [
        f"{module} imports {sorted(names & forbidden)}"
        for module, names in _imports(package).items()
        if names & forbidden
    ]


APPS = {"common", "commerce", "offers", "core", "promotions", "pricing", "scrapers"}


class ImportBoundaryTests(SimpleTestCase):
    """Each app imports only what sits below it."""

    def test_commerce_imports_only_common(self) -> None:
        """Commerce is the neutral base."""
        assert _violations("commerce", APPS - {"common", "commerce"}) == []

    def test_offers_never_imports_the_catalog_or_above(self) -> None:
        """Offers know markets and sellers, never products or promotions."""
        allowed = {"common", "commerce", "offers"}
        assert _violations("offers", APPS - allowed) == []

    def test_normalizers_never_import_django_models(self) -> None:
        """A normalizer is payload in, DTO out."""
        forbidden = {"django", *APPS}
        assert _violations("scrapers/normalizers", forbidden) == []
