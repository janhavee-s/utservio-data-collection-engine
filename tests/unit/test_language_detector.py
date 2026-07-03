"""Tests for language detection."""

from app.parsers.language_detector import LanguageDetector, LanguageResult


class TestLanguageDetector:
    def setup_method(self) -> None:
        self.detector = LanguageDetector()

    def test_detects_english_from_html_tag(self) -> None:
        html = '<html lang="en"><head></head><body><p>Hello world</p></body></html>'
        result = self.detector.detect(html)
        assert result.language == "en"
        assert result.source == "html_tag"
        assert result.confidence >= 0.9

    def test_detects_spanish_from_html_tag(self) -> None:
        html = '<html lang="es"><head></head><body><p>Hola mundo</p></body></html>'
        result = self.detector.detect(html)
        assert result.language == "es"
        assert result.source == "html_tag"

    def test_detects_from_meta_content_language(self) -> None:
        html = '<html><head><meta http-equiv="content-language" content="fr"></head><body></body></html>'
        result = self.detector.detect(html)
        assert result.language == "fr"
        assert result.source == "meta_tag"

    def test_detects_from_meta_language(self) -> None:
        html = '<html><head><meta name="language" content="de"></head><body></body></html>'
        result = self.detector.detect(html)
        assert result.language == "de"
        assert result.source == "meta_tag"

    def test_detects_english_from_text(self) -> None:
        html = """
        <html><head></head><body>
        <p>The quick brown fox jumps over the lazy dog.
        This is a test of the English language detection system.
        We are checking if the algorithm can identify common English words
        and determine the language of the page content correctly.</p>
        </body></html>
        """
        result = self.detector.detect(html)
        assert result.language == "en"
        assert result.source == "text_analysis"
        assert result.confidence >= 0.3

    def test_detects_german_from_text(self) -> None:
        html = """
        <html><head></head><body>
        <p>Der schnelle braune Fuchs springt über den faulen Hund.
        Das ist ein Test der deutschen Spracherkennung.
        Wir prüfen, ob der Algorithmus deutsche Wörter erkennen kann.</p>
        </body></html>
        """
        result = self.detector.detect(html)
        assert result.language == "de"

    def test_defaults_to_english_when_no_signal(self) -> None:
        html = "<html><head></head><body><p>123 456 789</p></body></html>"
        result = self.detector.detect(html)
        assert result.language in ("en", "es", "fr", "de", "pt")

    def test_result_dataclass(self) -> None:
        result = LanguageResult(language="en", confidence=0.9, source="html_tag")
        assert result.language == "en"
        assert result.confidence == 0.9
        assert result.source == "html_tag"
