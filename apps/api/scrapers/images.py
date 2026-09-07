"""Normalize image references from stored merchant and schema.org payloads."""

from urllib.parse import urljoin, urlsplit

IMAGE_KEYS = frozenset(
    {
        "image",
        "images",
        "imageurl",
        "imageurlhttps",
        "image_url",
        "featured_image",
        "thumbnail",
        "thumbnailurl",
        "og:image",
    },
)
URL_KEYS = frozenset({"src", "url", "contenturl", "content", "@id"})
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg")
PROPERTY_PAIR_LENGTH = 2


def image_urls(value: object, *, base_url: str) -> list[str]:
    """Collect image-labelled references and image files, preserving source order."""
    return list(dict.fromkeys(_collect(value, base_url=base_url)))


def _image_reference(value: str, *, base_url: str, labelled: bool) -> list[str]:
    """Accept valid HTTP image references and discard empty or malformed values."""
    if not value.strip():
        return []
    try:
        url = urljoin(base_url, value.strip())
        parsed = urlsplit(url)
    except ValueError:
        return []
    is_image_file = parsed.path.lower().endswith(IMAGE_EXTENSIONS)
    if (
        parsed.scheme in {"http", "https"}
        and parsed.netloc
        and (labelled or is_image_file)
    ):
        return [url]
    return []


def _collect(
    value: object,
    *,
    base_url: str,
    image_context: bool = False,
) -> list[str]:
    """Walk nested payloads while tracking image-labelled fields."""
    if isinstance(value, str):
        return _image_reference(value, base_url=base_url, labelled=image_context)
    if isinstance(value, list):
        # OpenGraph properties can be represented as [property, content] pairs.
        if (
            len(value) == PROPERTY_PAIR_LENGTH
            and isinstance(value[0], str)
            and value[0].lower() in IMAGE_KEYS
        ):
            return _collect(value[1], base_url=base_url, image_context=True)
        return [
            url
            for nested in value
            for url in _collect(nested, base_url=base_url, image_context=image_context)
        ]
    if not isinstance(value, dict):
        return []
    is_image_object = value.get("@type") == "ImageObject"
    urls: list[str] = []
    for key, nested in value.items():
        label = str(key).lower()
        labelled = label in IMAGE_KEYS or (
            (image_context or is_image_object) and label in URL_KEYS
        )
        urls.extend(_collect(nested, base_url=base_url, image_context=labelled))
    return urls
