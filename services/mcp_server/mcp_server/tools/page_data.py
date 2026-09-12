"""Local parsing of rendered HTML captured by Django."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup


def _visible_text(soup: BeautifulSoup) -> str:
    """Return the visible text with one node per line.

    The line breaks are the point: a nutrition table laid out in divs is only
    readable if each label and value keeps its own line. Collapsing the page
    into one space-separated run loses the row structure that makes those
    values parseable at all.
    """
    for element in soup.find_all(["script", "style", "noscript", "template"]):
        element.decompose()
    lines = (line.strip() for line in soup.get_text("\n").splitlines())
    return "\n".join(line for line in lines if line)


def parse_raw_html(raw_html: str, *, base_url: str | None = None) -> dict[str, object]:
    """Extract tables, visible text, and image references from captured HTML."""
    soup = BeautifulSoup(raw_html, "html.parser")
    tables: list[list[list[str]]] = []
    for table in soup.find_all("table"):
        rows: list[list[str]] = []
        for row in table.find_all("tr"):
            cells = [
                cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])
            ]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)

    images: list[dict[str, str | None]] = []
    for image in soup.find_all("img"):
        source = image.get("src") or image.get("data-src") or image.get("data-original")
        if not source:
            continue
        images.append(
            {
                "url": urljoin(base_url, source) if base_url else source,
                "alt": image.get("alt"),
            },
        )

    return {
        "text": _visible_text(soup),
        "tables": tables,
        "images": images,
    }
