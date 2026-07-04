"""Shared utilities for parsing strategies.

Contains common functions used across multiple strategies:
- Price parsing and currency detection
- Social platform domain mapping
- Record validation (FAQ, nav, low-quality filtering)
"""

import re
from urllib.parse import urlparse

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
        parse_price("₹799") -> 799.0
        parse_price("Free") -> None
    """
    if not price_text:
        return None
    cleaned = price_text.replace(",", "").replace("\xa0", "")
    numbers = re.findall(r"\d+\.?\d*", cleaned)
    if numbers:
        try:
            val = float(numbers[0])
            if val == 0:
                return None
            return val
        except ValueError:
            return None
    return None


def detect_currency(price_text: str | None) -> str:
    """Detect currency from price text.

    Examples:
        detect_currency("$99.99") -> "USD"
        detect_currency("€1,299") -> "EUR"
        detect_currency("₹799") -> "INR"
        detect_currency("Rs. 499") -> "INR"
    """
    if not price_text:
        return "USD"
    if "₹" in price_text or "Rs" in price_text or "INR" in price_text.upper():
        return "INR"
    if "$" in price_text:
        return "USD"
    if "€" in price_text:
        return "EUR"
    if "£" in price_text:
        return "GBP"
    return "USD"


def detect_currency_from_url(url: str) -> str:
    """Detect likely currency from domain TLD.

    Indian domains (.in, urbancompany.com, snabbit.com, etc.) -> INR
    US domains (.com, .us) -> USD
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""

    # Indian domains
    indian_domains = (
        "urbancompany.com",
        "snabbit.com",
        "kamkaka.com",
        "withpronto.com",
        "oyekar.com",
        "hicare.in",
    )
    for domain in indian_domains:
        if domain in host:
            return "INR"

    indian_tlds = (".in",)
    for tld in indian_tlds:
        if host.endswith(tld):
            return "INR"

    # Default to USD for all other domains
    return "USD"


# ─── Record Validation ──────────────────────────────────────────────

# Keywords that indicate non-service content
_SKIP_SERVICE_NAMES: set[str] = {
    "how to book", "who fulfils", "faq", "frequently asked",
    "help center", "support", "contact us", "contact",
    "terms", "privacy", "cookie", "legal",
    "login", "log in", "sign in", "register", "sign up",
    "home", "about", "about us", "careers", "jobs",
    "download app", "get the app", "refer", "partner",
    "customer care", "helpline",
    # Section headings (not actual services)
    "in the spotlight", "new and noteworthy", "most booked services",
    "cleaning essentials", "appliance repair & service", "massage for men",
    "home repair & installation", "beauty services", "wellness services",
    "what we do", "our services", "popular services", "trending services",
    "all services", "browse services", "explore services",
    "view all", "see all", "show more", "load more",
}

# Patterns that indicate FAQ/help content
_SERVICE_NAME_BLACKLIST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^(how|what|why|when|where|who|can|do|does|is|are|will|should)\s", re.I),
    re.compile(r"\?$"),
    re.compile(r"^(faq|help|support|contact|terms|privacy|cookie)", re.I),
    re.compile(r"^(login|sign\s?(in|up)|register|account)", re.I),
    re.compile(r"^(home|about|menu|navigation|footer|header|skip)", re.I),
    re.compile(r"^(download|app\s|get\s|install)", re.I),
    re.compile(r"^(t&c|refund|cancell|grievance|sitemap)", re.I),
]


def is_valid_service_name(name: str | None) -> bool:
    """Check if a service name looks like a real service (not FAQ/nav/help)."""
    if not name or len(name.strip()) < 2:
        return False
    normalized = name.strip().lower()
    if normalized in _SKIP_SERVICE_NAMES:
        return False
    for pattern in _SERVICE_NAME_BLACKLIST_PATTERNS:
        if pattern.search(normalized):
            return False
    if len(normalized) > 200:
        return False
    return True


def is_valid_pricing_entry(
    service_name: str | None,
    base_price: float | None,
) -> bool:
    """Reject placeholder pricing entries."""
    if not service_name:
        return False
    lower = service_name.strip().lower()
    placeholders = {
        "detected service", "detected price", "unknown", "service",
        "price", "cost", "rate", "fee",
    }
    if lower in placeholders:
        return False
    if base_price is not None and base_price <= 0:
        return False
    return True


def is_valid_content_title(title: str | None) -> bool:
    """Reject low-quality content titles."""
    if not title or len(title.strip()) < 5:
        return False
    lower = title.strip().lower()
    skip = {
        "untitled", "blog", "news", "articles", "resources",
        "read more", "click here", "learn more", "see all",
    }
    if lower in skip:
        return False
    if lower.endswith("?"):
        return False
    return True


# ─── Indian City Detection ──────────────────────────────────────────

_INDIAN_CITIES: list[str] = [
    "mumbai", "bangalore", "bengaluru", "delhi", "new delhi",
    "hyderabad", "chennai", "pune", "kolkata", "ahmedabad",
    "jaipur", "lucknow", "chandigarh", "bhopal", "indore",
    "nagpur", "patna", "vadodara", "surat", "rajkot",
    "coimbatore", "kochi", "thiruvananthapuram", "goa",
    "noida", "gurugram", "gurgaon", "faridabad", "ghaziabad",
]


def detect_indian_cities(text: str | None) -> list[str]:
    """Detect Indian cities mentioned in text."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for city in _INDIAN_CITIES:
        if city in text_lower and city not in found:
            found.append(city)
    return found


# Country detection from text
_COUNTRY_KEYWORDS: list[tuple[str, str]] = [
    ("india", "IN"), ("united states", "US"), ("usa", "US"), ("united kingdom", "UK"),
    ("uk", "UK"), ("canada", "CA"), ("australia", "AU"), ("germany", "DE"),
    ("france", "FR"), ("japan", "JP"), ("china", "CN"), ("brazil", "BR"),
    ("singapore", "SG"), ("uae", "AE"), ("dubai", "AE"), ("saudi arabia", "SA"),
]


def detect_countries(text: str | None) -> list[str]:
    """Detect operating countries from text content."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for keyword, code in _COUNTRY_KEYWORDS:
        if keyword in text_lower and code not in found:
            found.append(code)
    return found


# Username extraction patterns per platform
_SOCIAL_USERNAME_PATTERNS: dict[str, re.Pattern[str]] = {
    "linkedin": re.compile(r"linkedin\.com/(?:in|company)/([a-zA-Z0-9_-]+)"),
    "facebook": re.compile(r"facebook\.com/([a-zA-Z0-9._-]+)"),
    "instagram": re.compile(r"instagram\.com/([a-zA-Z0-9._]+)"),
    "twitter": re.compile(r"(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)"),
    "youtube": re.compile(r"youtube\.com/(?:@|channel/|c/)([a-zA-Z0-9_-]+)"),
    "pinterest": re.compile(r"pinterest\.com/([a-zA-Z0-9_]+)"),
    "threads": re.compile(r"threads\.net/@([a-zA-Z0-9._]+)"),
}


def extract_social_username(platform: str, url: str) -> str | None:
    """Extract username from a social media profile URL."""
    pattern = _SOCIAL_USERNAME_PATTERNS.get(platform)
    if not pattern:
        return None
    match = pattern.search(url)
    return match.group(1) if match else None
