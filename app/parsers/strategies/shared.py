"""Shared utilities for parsing strategies.

Contains common functions used across multiple strategies:
- Price parsing and currency detection
- Social platform domain mapping
"""

import re

# Social platform domain mapping (used by multiple strategies)
SOCIAL_PLATFORM_DOMAINS: dict[str, str] = {
    "linkedin.com": "linkedin",
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "youtube.com": "youtube",
    "pinterest.com": "pinterest",
    "threads.net": "threads",
}


def parse_price(price_text: str | None) -> float | None:
    """Extract numeric price from text.

    Examples:
        parse_price("$99.99") -> 99.99
        parse_price("€1,299") -> 1299.0
        parse_price("From $49/mo") -> 49.0
        parse_price("Free") -> None
    """
    if not price_text:
        return None
    numbers = re.findall(r"[\d,]+\.?\d*", price_text.replace(",", ""))
    if numbers:
        try:
            return float(numbers[0])
        except ValueError:
            return None
    return None


def detect_currency(price_text: str | None) -> str:
    """Detect currency from price text.

    Examples:
        detect_currency("$99.99") -> "USD"
        detect_currency("€1,299") -> "EUR"
        detect_currency("£50") -> "GBP"
    """
    if not price_text:
        return "USD"
    if "$" in price_text:
        return "USD"
    if "€" in price_text:
        return "EUR"
    if "£" in price_text:
        return "GBP"
    if "₹" in price_text:
        return "INR"
    return "USD"
