from django import template

register = template.Library()


@register.filter
def tag_classes(tag_name: str | None) -> str:
    """Return DaisyUI modifier classes for a given tag name."""
    if not tag_name:
        return "badge-neutral"

    tag_name = tag_name.lower()

    modifiers = {
        "whey": "badge-primary",
        "pea": "badge-success",
        "soy": "badge-warning",
        "rice": "badge-accent",
        "hemp": "badge-secondary",
        "plant": "badge-success",
    }

    for key, value in modifiers.items():
        if key in tag_name:
            return value

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
