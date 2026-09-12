"""Tests for local parsing of captured page HTML."""

from mcp_server.tools.page_data import parse_raw_html


def test_parse_raw_html_extracts_tables_text_and_images() -> None:
    """Extract visible evidence while ignoring script noise."""
    html = """
    <html><body>
      <script>window.noise = 'ignore me'</script>
      <table><tr><th>Serving</th><th>30 g</th></tr>
        <tr><td>Protein</td><td>24 g</td></tr></table>
      <div>Visible nutrition note</div>
      <img src="/media/label.jpg" alt="Nutrition label">
    </body></html>
    """

    result = parse_raw_html(html, base_url="https://example.com/product")

    assert result["tables"] == [
        [
            ["Serving", "30 g"],
            ["Protein", "24 g"],
        ]
    ]
    # One node per line, so a label keeps its value on the next line and a
    # table laid out in divs stays readable.
    assert result["text"].splitlines() == [
        "Serving",
        "30 g",
        "Protein",
        "24 g",
        "Visible nutrition note",
    ]
    assert result["images"] == [
        {"url": "https://example.com/media/label.jpg", "alt": "Nutrition label"},
    ]
    assert "ignore me" not in result["text"]
