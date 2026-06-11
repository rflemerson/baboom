from mcp_server.tools.dynamic_crawler import extract_page_data

SAMPLE_HTML = """
<html>
<head>
<title> 3W Whey Protein 1Kg - Growth Supplements </title>
<meta property="og:title" content="3W Whey Protein 1Kg">
<meta property="og:image" content="https://cdn.example.com/produto/mockup.webp">
<meta name="description" content="Blend de whey concentrado e isolado.">
<meta name="empty-content" content="">
<script type="application/ld+json">
{"@type": "Product", "name": "3W Whey", "image": "https://cdn.example.com/produto/foto.jpg",
 "offers": {"@type": "Offer", "price": "129.90"}}
</script>
<script type="application/ld+json">[{"@type": "BreadcrumbList"}]</script>
<script type="application/ld+json">not valid json</script>
</head>
<body>
<img src="//cdn.example.com/produto/galeria.jpg" alt="Galeria do produto">
<img data-src="/upload/produto/lazy.png">
<img src="https://cdn.example.com/produto/foto.jpg" alt="Foto principal">
<img src="data:image/gif;base64,R0lGOD==">
<table>
  <tr><th>Porção</th><th>30 g</th></tr>
  <tr><td>Proteínas</td><td>24 g</td></tr>
</table>
<table><tr><td></td></tr></table>
</body>
</html>
"""

BASE_URL = "https://www.gsuplementos.com.br/produto-p1"


def test_extracts_title_and_meta():
    data = extract_page_data(SAMPLE_HTML, base_url=BASE_URL)

    assert data["title"] == "3W Whey Protein 1Kg - Growth Supplements"
    assert data["meta"]["og:title"] == "3W Whey Protein 1Kg"
    assert data["meta"]["description"] == "Blend de whey concentrado e isolado."
    assert "empty-content" not in data["meta"]


def test_extracts_json_ld_blocks():
    data = extract_page_data(SAMPLE_HTML, base_url=BASE_URL)

    types = [block.get("@type") for block in data["jsonLd"]]
    assert types == ["Product", "BreadcrumbList"]
    assert data["jsonLd"][0]["offers"]["price"] == "129.90"


def test_extracts_tables_skipping_empty_ones():
    data = extract_page_data(SAMPLE_HTML, base_url=BASE_URL)

    assert data["tables"] == [[["Porção", "30 g"], ["Proteínas", "24 g"]]]


def test_extracts_images_with_neutral_metadata():
    data = extract_page_data(SAMPLE_HTML, base_url=BASE_URL)

    by_url = {image["url"]: image for image in data["images"]}

    assert set(by_url) == {
        "https://cdn.example.com/produto/mockup.webp",
        "https://cdn.example.com/produto/foto.jpg",
        "https://cdn.example.com/produto/galeria.jpg",
        "https://www.gsuplementos.com.br/upload/produto/lazy.png",
    }

    assert by_url["https://cdn.example.com/produto/mockup.webp"]["sources"] == [
        "meta:og:image",
    ]
    # Same URL referenced by JSON-LD and an <img>: both sources, alt kept.
    foto = by_url["https://cdn.example.com/produto/foto.jpg"]
    assert foto["sources"] == ["jsonld:Product", "html:img"]
    assert foto["alt"] == "Foto principal"
    assert by_url["https://cdn.example.com/produto/galeria.jpg"]["alt"] == (
        "Galeria do produto"
    )


def test_empty_html():
    data = extract_page_data("<html></html>")

    assert data == {
        "title": None,
        "meta": {},
        "jsonLd": [],
        "tables": [],
        "images": [],
    }
