"""URL normalization for consistent duplicate detection.

Canonical URL normalization ensures that functionally identical URLs
are reduced to a single canonical form before comparison or hashing.
"""

import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

# Query parameters to strip during normalization (tracking/analytics noise)
_STRIP_PARAMS: set[str] = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_cid",
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "gbraid",
    "wbraid",
    "msclkid",
    "twclid",
    "li_fat_id",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
    "_ga",
    "_gl",
    "yclid",
    "igshid",
    "oly_anon_id",
    "oly_enc_id",
    "_hsenc",
    "_hsmi",
    "mkt_tok",
    "hsa_cam",
    "hsa_grp",
    "hsa_mt",
    "hsa_src",
    "hsa_ad",
    "hsa_acc",
    "hsa_net",
    "hsa_ver",
    "hsa_la",
    "hsa_ol",
    "hsa_kw",
    "hsa_tgt",
    "hsa_bal",
    "hsa_bet",
    "hsa_bot",
    "hsa_pst",
    "hsa_adid",
    "hsa_cam_id",
    "hsa_net_id",
    "hsa_ver_id",
    "pk_campaign",
    "pk_kwd",
    "pk_source",
    "pk_medium",
}


def normalize_url(url: str, *, base_url: str | None = None) -> str:
    """Normalize a URL to its canonical form.

    Steps:
        1. Resolve relative URLs against base_url
        2. Lowercase scheme and host
        3. Strip default ports (80/443)
        4. Remove duplicate slashes in path
        5. Remove trailing slash from path (except root)
        6. Sort query parameters
        7. Strip tracking parameters (utm_*, fbclid, gclid, etc.)
        8. Remove fragment identifiers
        9. Remove www. prefix from host

    Args:
        url: The URL to normalize.
        base_url: Optional base URL for resolving relative paths.

    Returns:
        The canonical URL string.
    """
    if not url:
        return url

    if base_url:
        url = urljoin(base_url, url)

    parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path
    path = re.sub(r"//+", "/", path)
    if path == "/":
        pass
    elif path.endswith("/"):
        path = path.rstrip("/")

    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered_params = {k: v for k, v in query_params.items() if k.lower() not in _STRIP_PARAMS}
    sorted_query = urlencode(sorted(filtered_params.items()), doseq=True)

    normalized = urlunparse(
        (
            scheme,
            netloc,
            path,
            parsed.params,
            sorted_query,
            "",
        )
    )

    return normalized


def normalize_content_url(url: str, *, base_url: str | None = None) -> str:
    """Normalize a content URL for deduplication.

    Strips trailing slashes except for domain root.
    """
    normalized = normalize_url(url, base_url=base_url)
    from urllib.parse import urlparse as _urlparse

    parsed = _urlparse(normalized)
    if parsed.path != "/" and normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    return normalized


def extract_canonical_url(html: str, page_url: str) -> str | None:
    """Extract canonical URL from HTML.

    Looks for:
    - <link rel="canonical" href="...">
    - <meta property="og:url" content="...">
    - <link rel="alternate" hreflang="..." href="...">

    Returns the canonical URL normalized, or None if not found.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    canonical_tag = soup.find("link", rel="canonical")
    if canonical_tag:
        href = canonical_tag.get("href")
        if href:
            return normalize_url(str(href), base_url=page_url)

    og_url_tag = soup.find("meta", property="og:url")
    if og_url_tag:
        content = og_url_tag.get("content")
        if content:
            return normalize_url(str(content), base_url=page_url)

    return None


def is_tracking_url(url: str) -> bool:
    """Check if a URL contains tracking parameters."""
    parsed = urlparse(url)
    if not parsed.query:
        return False
    params = parse_qs(parsed.query)
    return any(k.lower() in _STRIP_PARAMS for k in params)
