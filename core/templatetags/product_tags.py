from django import template

register = template.Library()


@register.filter
def tag_classes(tag_name: str | None) -> str:
    """Return DaisyUI modifier classes for a given tag name."""
    if not tag_name:
        return "badge-neutral"

    tag_name = tag_name.lower()

    if "whey" in tag_name:
        return "badge-primary"
    if "pea" in tag_name:
        return "badge-success"
    if "soy" in tag_name:
        return "badge-warning"
    if "rice" in tag_name:
        return "badge-accent"
    if "hemp" in tag_name:
        return "badge-secondary"
    if "plant" in tag_name:
        return "badge-success"

    return "badge-neutral"


@register.filter
def category_classes(category_name: str | None) -> str:
    """Return DaisyUI modifier classes for a given category name."""
    if not category_name:
        return "badge-neutral"

    category_name = category_name.lower()

    if "animal" in category_name:
        return "badge-error"
    if "plant" in category_name:
        return "badge-success"
    if "blend" in category_name:
        return "badge-info"

    return "badge-neutral"
