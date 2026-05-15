from __future__ import annotations


def short_restaurant_name(value: str | None) -> str:
    if not value:
        return "Palate"
    normalized = " ".join(value.replace("\n", " ").split())
    if not normalized:
        return "Palate"
    separators = [",", "|", " - ", " at "]
    for separator in separators:
        if separator in normalized:
            normalized = normalized.split(separator, 1)[0].strip()
            break
    return normalized[:80] or "Palate"


def display_customer_name(value: str | None) -> str:
    if not value:
        return "there"
    normalized = " ".join(value.replace("\n", " ").split()).strip()
    if not normalized:
        return "there"
    return normalized[:60]
