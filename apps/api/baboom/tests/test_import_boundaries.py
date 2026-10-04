"""The dependency rules of the pricing domain, checked on the source."""

from __future__ import annotations

import ast
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]


def _imports(package: str) -> dict[str, set[str]]:
    """Return the absolute modules each module of a package imports."""
    found: dict[str, set[str]] = {}
    for path in (ROOT / package).rglob("*.py"):
        if "migrations" in path.parts or "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names.add(node.module)
        found[str(path.relative_to(ROOT))] = names
    return found


def _violations(
    package: str,
    forbidden: set[str],
    allowed_paths: tuple[str, ...] = (),
) -> list[str]:
    """List imports of forbidden top-level packages, except pure promotion rules."""
    found = []
    for module, names in _imports(package).items():
        if module.startswith(allowed_paths):
            continue
        bad = sorted(
            name
            for name in names
            if name.split(".")[0] in forbidden and not name.startswith(RULES)
        )
        if bad:
            found.append(f"{module} imports {bad}")
    return found


# The one module of an app any layer may import: it imports nothing back.
RULES = "promotions.rules"


APPS = {
    "common",
    "commerce",
    "offers",
    "core",
    "promotions",
    "pricing",
    "scrapers",
}


class ImportBoundaryTests(SimpleTestCase):
    """Each app imports only what sits below it."""

    def test_commerce_imports_only_common(self) -> None:
        """Commerce is the neutral base."""
        assert _violations("commerce", APPS - {"common", "commerce"}) == []

    def test_offers_never_imports_the_catalog_or_above(self) -> None:
        """Offers know markets and sellers, never products or promotions."""
        allowed = {"common", "commerce", "offers"}
        assert _violations("offers", APPS - allowed) == []

    def test_core_never_imports_promotions_or_pricing(self) -> None:
        """The catalog does not know the rules that price it; its REST view composes.

        The public view chooses the price source; models and selectors only
        take one as a parameter.
        """
        forbidden = {"promotions", "pricing", "scrapers"}
        assert _violations("core", forbidden, allowed_paths=("core/rest/",)) == []

    def test_promotions_import_no_pricing_or_scrapers(self) -> None:
        """Curated rules sit below the engine and above the facts."""
        assert _violations("promotions", {"pricing", "scrapers"}) == []

    def test_the_pricing_engine_imports_no_framework_or_app(self) -> None:
        """The engine is pure: no Django, no database, no app but promotion rules."""
        forbidden = {"django", "pydantic", *APPS}
        assert _violations("pricing/domain", forbidden) == []

    def test_promotion_rules_import_nothing(self) -> None:
        """Rules stay pure, so the engine may read them; any import breaks that."""
        forbidden = {"django", "pydantic", *APPS}
        assert _violations("promotions/rules", forbidden) == []

    def test_normalizers_never_import_django_models(self) -> None:
        """A normalizer is payload in, DTO out."""
        forbidden = {"django", *APPS}
        assert _violations("scrapers/normalizers", forbidden) == []
