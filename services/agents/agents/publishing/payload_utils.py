"""Payload-shaping helpers used by the publishing stage."""

from __future__ import annotations

import re

NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Normalize free text into a stable slug."""
    normalized = NON_ALNUM_PATTERN.sub("-", value.lower()).strip("-")
    return normalized or "item"


def to_graphql_stock_status(status: str | None) -> str:
    """Map scraper stock status values into the GraphQL enum."""
    stock_map = {
        "A": "AVAILABLE",
        "L": "LAST_UNITS",
        "O": "OUT_OF_STOCK",
        "AVAILABLE": "AVAILABLE",
        "LAST_UNITS": "LAST_UNITS",
        "OUT_OF_STOCK": "OUT_OF_STOCK",
    }
    return stock_map.get((status or "").upper(), "AVAILABLE")


def parse_number(value: object) -> float | None:
    """Parse numbers from LLM/API values like '30g', '1,5', or 'N/A'."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    parsed = match.group(0) if match else ""
    if not parsed:
        return None
    try:
        return float(parsed)
    except (TypeError, ValueError):
        return None


def to_float(value: object, default: float = 0.0) -> float:
    """Convert to float with default fallback."""
    parsed = parse_number(value)
    return parsed if parsed is not None else default


def to_int(value: object, default: int = 0) -> int:
    """Convert to int with default fallback."""
    parsed = parse_number(value)
    if parsed is None:
        return default
    return int(parsed)


def build_nutrition_payload(analysis_data: dict) -> list[dict]:
    """Map structured analysis nutrition facts into GraphQL payload shape."""
    nutrition = analysis_data.get("nutrition_facts")
    if not nutrition:
        return []

    micronutrients = [
        {
            "name": micronutrient.get("name"),
            "value": to_float(micronutrient.get("value")),
            "unit": micronutrient.get("unit") or "mg",
        }
        for micronutrient in (nutrition.get("micronutrients") or [])
        if micronutrient.get("name")
    ]

    return [
        {
            "flavorNames": analysis_data.get("flavor_names") or [],
            "nutritionFacts": {
                "description": analysis_data.get("variant_name") or "AI Analysis",
                "servingSizeGrams": to_float(nutrition.get("serving_size_grams")),
                "energyKcal": to_int(nutrition.get("energy_kcal")),
                "proteins": to_float(nutrition.get("proteins")),
                "carbohydrates": to_float(nutrition.get("carbohydrates")),
                "totalSugars": to_float(nutrition.get("total_sugars")),
                "addedSugars": to_float(nutrition.get("added_sugars")),
                "totalFats": to_float(nutrition.get("total_fats")),
                "saturatedFats": to_float(nutrition.get("saturated_fats")),
                "transFats": to_float(nutrition.get("trans_fats")),
                "dietaryFiber": to_float(nutrition.get("dietary_fiber")),
                "sodium": to_float(nutrition.get("sodium")),
                "micronutrients": micronutrients,
            },
        },
    ]
