from typing import ClassVar
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.parsers.strategies.shared import SOCIAL_PLATFORM_DOMAINS
from app.parsers.strategy import ParsedResult, ParsingStrategy


class MetadataStrategy(ParsingStrategy):
    @property
    def name(self) -> str:
        return "metadata"

    @property
    def weight(self) -> float:
        return 0.10

    SOCIAL_PLATFORMS: ClassVar[dict[str, str]] = {
        "og:site_name": "",
        "twitter:site": "twitter",
        "twitter:creator": "twitter",
    }

    def parse(self, soup: BeautifulSoup, url: str) -> ParsedResult:
        result = ParsedResult()
        self._extract_og_tags(soup, result, url)
        self._extract_twitter_tags(soup, result)
        self._extract_meta_description(soup, result)
        self._extract_meta_keywords(soup, result)
        self._extract_favicon(soup, result, url)
        return result

    def _extract_og_tags(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        og_name = self._get_meta_content(soup, "meta[property='og:site_name']")
        if og_name and not result.company_name:
            result.company_name = og_name
        og_desc = self._get_meta_content(soup, "meta[property='og:description']")
        if og_desc and not result.description:
            result.description = og_desc
        og_image = self._get_meta_content(soup, "meta[property='og:image']")
        if og_image and not result.logo:
            result.logo = urljoin(url, og_image)
        og_url = self._get_meta_content(soup, "meta[property='og:url']")
        if og_url:
            for domain, platform in self._social_platforms().items():
                if domain in og_url and platform not in result.social_links:
                    result.social_links[platform] = og_url

    def _extract_twitter_tags(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        twitter_site = self._get_meta_content(soup, "meta[name='twitter:site']")
        if twitter_site and not result.social_links.get("twitter"):
            if twitter_site.startswith("@"):
                twitter_site = "https://twitter.com/" + twitter_site[1:]
            elif twitter_site.startswith("http"):
                pass
            else:
                twitter_site = "https://twitter.com/" + twitter_site
            result.social_links["twitter"] = twitter_site

    def _extract_meta_description(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        if result.description:
            return
        desc = self._get_meta_content(soup, "meta[name='description']")
        if desc:
            result.description = desc

    def _extract_meta_keywords(self, soup: BeautifulSoup, result: ParsedResult) -> None:
        if result.industry:
            return
        keywords = self._get_meta_content(soup, "meta[name='keywords']")
        if keywords:
            kw_list = [k.strip().lower() for k in keywords.split(",")]
            industry_keywords = [
                "home services",
                "cleaning",
                "plumbing",
                "electrical",
                "hvac",
                "repair",
                "maintenance",
                "installation",
            ]
            for kw in kw_list:
                if kw in industry_keywords:
                    result.industry = kw
                    break

    def _extract_favicon(self, soup: BeautifulSoup, result: ParsedResult, url: str) -> None:
        if result.logo:
            return
        for selector in [
            "link[rel='icon']",
            "link[rel='shortcut icon']",
            "link[rel='apple-touch-icon']",
        ]:
            link = soup.select_one(selector)
            if link:
                href = str(link.get("href", ""))
                if href:
                    result.logo = urljoin(url, href)
                    return

    def _get_meta_content(self, soup: BeautifulSoup, selector: str) -> str | None:
        element = soup.select_one(selector)
        if element:
            content = str(element.get("content", ""))
            if content:
                return content
        return None

    def _social_platforms(self) -> dict[str, str]:
        return SOCIAL_PLATFORM_DOMAINS
