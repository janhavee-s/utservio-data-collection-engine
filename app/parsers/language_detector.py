"""Language Detection — automatically detect page language.

Detects page language from:
- HTML lang attribute
- Meta tags (content-language)
- Text content analysis

Stores language, confidence, and detection source.
Supports multilingual websites.
Does not translate content — metadata only.
"""

import re
from dataclasses import dataclass

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)

COMMON_WORDS: dict[str, set[str]] = {
    "en": {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "has",
        "his",
        "how",
        "its",
        "may",
        "new",
        "now",
        "old",
        "see",
        "way",
        "who",
        "why",
        "did",
        "get",
        "let",
        "say",
        "she",
        "too",
        "use",
        "about",
        "after",
        "again",
        "being",
        "below",
        "could",
        "every",
        "first",
        "found",
        "great",
        "house",
        "large",
        "learn",
        "never",
        "other",
        "place",
        "plant",
        "point",
        "right",
        "small",
        "sound",
        "spell",
        "still",
        "study",
        "their",
        "there",
        "these",
        "thing",
        "think",
        "three",
        "water",
        "where",
        "which",
        "world",
        "would",
        "write",
    },
    "es": {
        "el",
        "la",
        "de",
        "en",
        "que",
        "los",
        "del",
        "las",
        "por",
        "con",
        "una",
        "para",
        "como",
        "más",
        "pero",
        "sus",
        "le",
        "ya",
        "o",
        "este",
        "ha",
        "sí",
        "porque",
        "esta",
        "son",
        "entre",
        "cuando",
        "muy",
        "sin",
        "sobre",
        "también",
        "me",
        "hasta",
        "hay",
        "donde",
        "quien",
        "desde",
        "todo",
        "nos",
        "durante",
        "todos",
        "uno",
        "les",
        "ni",
        "contra",
        "otros",
        "ese",
        "eso",
        "ante",
        "ellos",
        "e",
        "esto",
        "mí",
        "antes",
        "algunos",
    },
    "fr": {
        "le",
        "la",
        "de",
        "et",
        "les",
        "des",
        "un",
        "une",
        "du",
        "en",
        "que",
        "qui",
        "dans",
        "est",
        "pas",
        "pour",
        "sur",
        "sont",
        "avec",
        "plus",
        "par",
        "son",
        "mais",
        "tout",
        "comme",
        "nous",
        "vous",
        "ils",
        "elle",
        "ont",
        "fait",
        "peut",
        "bien",
        "aussi",
        "cette",
        "être",
        "avoir",
        "mon",
        "leur",
        "ces",
        "mes",
        "tes",
        "nos",
        "vos",
        "aux",
    },
    "de": {
        "der",
        "die",
        "und",
        "in",
        "den",
        "von",
        "zu",
        "das",
        "mit",
        "sich",
        "des",
        "auf",
        "für",
        "ist",
        "im",
        "dem",
        "nicht",
        "ein",
        "eine",
        "als",
        "auch",
        "es",
        "an",
        "werden",
        "aus",
        "er",
        "hat",
        "dass",
        "sie",
        "nach",
        "wird",
        "bei",
        "einer",
        "um",
        "am",
        "sind",
        "noch",
        "wie",
        "einem",
    },
    "pt": {
        "de",
        "que",
        "em",
        "um",
        "para",
        "com",
        "não",
        "uma",
        "os",
        "no",
        "se",
        "na",
        "por",
        "mais",
        "dos",
        "como",
        "mas",
        "foi",
        "ao",
        "ele",
        "das",
        "tem",
        "à",
        "seu",
        "sua",
        "ou",
        "ser",
        "quando",
        "muito",
        "há",
        "nos",
        "já",
        "está",
        "eu",
        "também",
        "só",
        "pelo",
        "pela",
    },
    "hi": {
        "के",
        "में",
        "है",
        "की",
        "एक",
        "और",
        "को",
        "यह",
        "पर",
        "से",
        "इस",
        "था",
        "ने",
        "कि",
        "वह",
        "क्या",
        "तो",
        "हैं",
        "या",
        "अब",
    },
    "ar": {
        "في",
        "من",
        "على",
        "هذا",
        "التي",
        "الذي",
        "إلى",
        "عن",
        "كان",
    },
    "ja": {
        "の",
        "に",
        "は",
        "を",
        "た",
        "が",
        "で",
        "て",
        "と",
        "し",
    },
    "zh": {
        "的",
        "一",
        "不",
        "在",
        "了",
        "有",
        "和",
        "人",
        "这",
        "中",
    },
}


@dataclass
class LanguageResult:
    """Result of language detection."""

    language: str
    confidence: float
    source: str  # "html_tag", "meta_tag", "text_analysis"


class LanguageDetector:
    """Detects page language from HTML and text content.

    Detection sources (in priority order):
    1. <html lang="..."> attribute
    2. <meta http-equiv="content-language" content="...">
    3. Text content word frequency analysis
    """

    def detect(self, html: str) -> LanguageResult:
        """Detect language of an HTML page."""
        soup = BeautifulSoup(html, "html.parser")

        lang = self._detect_from_html_tag(soup)
        if lang:
            return lang

        lang = self._detect_from_meta(soup)
        if lang:
            return lang

        return self._detect_from_text(soup)

    def _detect_from_html_tag(self, soup: BeautifulSoup) -> LanguageResult | None:
        """Detect language from <html lang="..."> attribute."""
        html_tag = soup.find("html")
        if html_tag:
            lang_attr = html_tag.get("lang") or html_tag.get("xml:lang")
            if lang_attr:
                lang_code = str(lang_attr).strip().lower()[:2]
                if lang_code in COMMON_WORDS or len(lang_code) == 2:
                    logger.debug("language_detected_from_html_tag", lang=lang_code)
                    return LanguageResult(
                        language=lang_code,
                        confidence=0.95,
                        source="html_tag",
                    )
        return None

    def _detect_from_meta(self, soup: BeautifulSoup) -> LanguageResult | None:
        """Detect language from meta tags."""
        meta = soup.find("meta", attrs={"http-equiv": re.compile(r"content-language", re.I)})
        if meta:
            content = meta.get("content", "")
            if content:
                lang_code = str(content).strip().lower()[:2]
                if lang_code in COMMON_WORDS or len(lang_code) == 2:
                    logger.debug("language_detected_from_meta", lang=lang_code)
                    return LanguageResult(
                        language=lang_code,
                        confidence=0.85,
                        source="meta_tag",
                    )

        meta_lang = soup.find("meta", attrs={"name": "language"})
        if meta_lang:
            content = meta_lang.get("content", "")
            if content:
                lang_code = str(content).strip().lower()[:2]
                if lang_code in COMMON_WORDS or len(lang_code) == 2:
                    return LanguageResult(
                        language=lang_code,
                        confidence=0.80,
                        source="meta_tag",
                    )

        return None

    def _detect_from_text(self, soup: BeautifulSoup) -> LanguageResult:
        """Detect language from text content word frequency."""
        text = soup.get_text(separator=" ", strip=True)
        words = set(re.findall(r"\b\w+\b", text.lower()))

        scores: dict[str, float] = {}
        for lang_code, common_word_set in COMMON_WORDS.items():
            overlap = len(words & common_word_set)
            total = len(common_word_set)
            if total > 0:
                scores[lang_code] = overlap / total

        if scores:
            best_lang = max(scores, key=scores.get)  # type: ignore[arg-type]
            best_score = scores[best_lang]
            confidence = min(0.9, best_score * 2)
            return LanguageResult(
                language=best_lang,
                confidence=max(0.3, confidence),
                source="text_analysis",
            )

        return LanguageResult(
            language="en",
            confidence=0.2,
            source="text_analysis",
        )
