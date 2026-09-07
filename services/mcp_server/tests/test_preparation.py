from mcp_server.tools.preparation import (
    build_prepared_context,
    extract_image_urls_from_html_text,
    extract_image_urls_from_payload,
    looks_like_image_url,
    normalize_url,
)


def test_looks_like_image_url():
    assert looks_like_image_url("https://cdn.example.com/a.jpg")
    assert looks_like_image_url("//cdn.example.com/a.webp?w=300")
    assert looks_like_image_url("/media/a.png")
    assert not looks_like_image_url("https://cdn.example.com/page.html")
    assert not looks_like_image_url("relative/a.jpg")


def test_normalize_url():
    assert normalize_url("//cdn.example.com/a.jpg") == "https://cdn.example.com/a.jpg"
    assert (
        normalize_url("/media/a.jpg", base_url="https://example.com/produto")
        == "https://example.com/media/a.jpg"
    )
    assert (
        normalize_url("media/a.jpg", base_url="https://example.com/loja/produto")
        == "https://example.com/loja/media/a.jpg"
    )
    assert normalize_url("https://x.com/a.jpg") == "https://x.com/a.jpg"


def test_extract_image_urls_from_payload_dedupes():
    payload = {
        "images": ["https://x.com/a.jpg", "https://x.com/a.jpg"],
        "nested": {"img": "//x.com/b.png", "other": 42},
    }

    assert extract_image_urls_from_payload(payload) == [
        "https://x.com/a.jpg",
        "https://x.com/b.png",
    ]


def test_extract_image_urls_from_html_text():
    html = '<img src="https://x.com/a.jpg?v=2"><img src="https://x.com/b.css">'

    assert extract_image_urls_from_html_text(html) == ["https://x.com/a.jpg?v=2"]
    assert extract_image_urls_from_html_text(None) == []


def test_build_prepared_context():
    item = {
        "id": "7",
        "storeSlug": "growth",
        "sourcePageUrl": "https://example.com/p",
        "productLink": "https://example.com/p",
        "name": "Whey",
        "price": "99.90",
        "stockStatus": "in_stock",
        "sourcePageContext": {"image": "https://x.com/a.jpg"},
        "sourcePageStructuredData": None,
        "imageUrls": ["https://x.com/extensionless", "https://x.com/a.jpg"],
    }

    prepared = build_prepared_context(item)

    assert prepared["itemId"] == "7"
    assert prepared["imageUrls"] == [
        "https://x.com/extensionless",
        "https://x.com/a.jpg",
    ]
    assert prepared["apiContext"] == {"image": "https://x.com/a.jpg"}
    assert prepared["structuredData"] is None
