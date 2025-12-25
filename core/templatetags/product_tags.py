from django import template

register = template.Library()


@register.filter
def tag_classes(tag_name: str | None) -> str:
    """Return Tailwind classes for a given tag name."""
    if not tag_name:
        return "bg-gray-500 text-white"

    tag_name = tag_name.lower()

    if "whey" in tag_name:
        return "bg-blue-600 text-white"
    if "pea" in tag_name:
        return "bg-emerald-600 text-white"
    if "soy" in tag_name:
        return "bg-amber-600 text-black"
    if "rice" in tag_name:
        return "bg-orange-500 text-white"
    if "hemp" in tag_name:
        return "bg-violet-600 text-white"
    if "plant" in tag_name:
        return "bg-lime-500 text-black"

    return "bg-gray-400 text-white"


@register.filter
def category_classes(category_name: str | None) -> str:
    """Return Tailwind classes for a given category name."""
    if not category_name:
        return "bg-gray-400 text-white"

    category_name = category_name.lower()

    if "animal" in category_name:
        return "bg-red-500 text-white"
    if "plant" in category_name:
        return "bg-green-400 text-black"
    if "blend" in category_name:
        return "bg-pink-500 text-white"

    return "bg-gray-400 text-white"
