from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup, Tag


@dataclass
class ParsedResult:
    company_name: str | None = None
    description: str | None = None
    logo: str | None = None
    industry: str | None = None
    headquarters: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    social_links: dict[str, str] = field(default_factory=dict)
    services: list[dict[str, Any]] = field(default_factory=list)
    pricing: list[dict[str, Any]] = field(default_factory=list)
    content: list[dict[str, Any]] = field(default_factory=list)
    social_profiles: list[dict[str, str | None]] = field(default_factory=list)
    confidence: float = 0.0
    strategy_results: dict[str, float] = field(default_factory=dict)
    _field_weights: dict[str, float] = field(default_factory=dict, repr=False)

    def _should_replace(self, field_name: str, new_weight: float) -> bool:
        """Determine if a new value should replace the existing one based on strategy weight."""
        current_weight = self._field_weights.get(field_name, 0.0)
        return new_weight > current_weight

    def merge(self, other: "ParsedResult", strategy_name: str, weight: float) -> None:
        # Scalar fields: replace if new strategy has higher weight
        if other.company_name:
            if self._should_replace("company_name", weight):
                self.company_name = other.company_name
                self._field_weights["company_name"] = weight
        if other.description:
            if self._should_replace("description", weight):
                self.description = other.description
                self._field_weights["description"] = weight
        if other.logo:
            if self._should_replace("logo", weight):
                self.logo = other.logo
                self._field_weights["logo"] = weight
        if other.industry:
            if self._should_replace("industry", weight):
                self.industry = other.industry
                self._field_weights["industry"] = weight
        if other.headquarters:
            if self._should_replace("headquarters", weight):
                self.headquarters = other.headquarters
                self._field_weights["headquarters"] = weight
        if other.contact_email:
            if self._should_replace("contact_email", weight):
                self.contact_email = other.contact_email
                self._field_weights["contact_email"] = weight
        if other.contact_phone:
            if self._should_replace("contact_phone", weight):
                self.contact_phone = other.contact_phone
                self._field_weights["contact_phone"] = weight

        # List fields: deduplicate and merge
        if other.social_links:
            for k, v in other.social_links.items():
                if k not in self.social_links:
                    self.social_links[k] = v
        if other.services:
            existing_names = {s.get("name") for s in self.services}
            for svc in other.services:
                if svc.get("name") and svc["name"] not in existing_names:
                    self.services.append(svc)
                    existing_names.add(svc["name"])
        if other.pricing:
            existing_names = {p.get("service_name") for p in self.pricing}
            for price in other.pricing:
                if price.get("service_name") and price["service_name"] not in existing_names:
                    self.pricing.append(price)
                    existing_names.add(price["service_name"])
        if other.content:
            existing_titles = {c.get("title") for c in self.content}
            for item in other.content:
                if item.get("title") and item["title"] not in existing_titles:
                    self.content.append(item)
                    existing_titles.add(item["title"])
        if other.social_profiles:
            existing_platforms = {p.get("platform") for p in self.social_profiles}
            for profile in other.social_profiles:
                if profile.get("platform") and profile["platform"] not in existing_platforms:
                    self.social_profiles.append(profile)
                    existing_platforms.add(profile["platform"])

        self.strategy_results[strategy_name] = weight
        self._recalculate_confidence()

    def _recalculate_confidence(self) -> None:
        """Calculate confidence based on fraction of fields populated, weighted by strategy quality."""
        scalar_fields = [
            "company_name", "description", "logo", "industry",
            "headquarters", "contact_email", "contact_phone",
        ]
        populated = sum(1 for f in scalar_fields if getattr(self, f))
        list_fields = ["services", "pricing", "content", "social_profiles", "social_links"]
        populated += sum(1 for f in list_fields if getattr(self, f))

        total_fields = len(scalar_fields) + len(list_fields)
        if total_fields == 0:
            self.confidence = 0.0
            return

        # Base confidence from field coverage
        field_coverage = populated / total_fields

        # Bonus from strategy weight (higher-weight strategies contribute more)
        weight_bonus = sum(self.strategy_results.values()) / max(len(self.strategy_results), 1)

        # Combined confidence: 70% field coverage + 30% strategy quality
        self.confidence = min(1.0, (field_coverage * 0.7) + (weight_bonus * 0.3))

    def to_company_dict(self) -> dict[str, Any]:
        return {
            "url": "",
            "name": self.company_name,
            "logo": self.logo,
            "description": self.description,
            "industry": self.industry,
            "headquarters": self.headquarters,
            "operating_countries": [],
            "operating_cities": [],
            "service_categories": [],
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "social_links": self.social_links,
        }

    def to_service_dict(self) -> dict[str, Any]:
        return {"url": "", "services": self.services}

    def to_pricing_dict(self) -> dict[str, Any]:
        return {"url": "", "pricing": self.pricing}

    def to_content_dict(self) -> dict[str, Any]:
        return {"url": "", "content": self.content}

    def to_social_dict(self) -> dict[str, Any]:
        profiles = list(self.social_profiles)
        existing_platforms = {p.get("platform") for p in profiles}
        for platform, url in self.social_links.items():
            if platform not in existing_platforms:
                profiles.append(
                    {
                        "platform": platform,
                        "profile_url": url,
                        "username": None,
                    }
                )
                existing_platforms.add(platform)
        return {"url": "", "social_profiles": profiles}


class ParsingStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def weight(self) -> float: ...

    @abstractmethod
    def parse(self, soup: BeautifulSoup, url: str) -> ParsedResult: ...

    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def _text(self, soup: BeautifulSoup | Tag, selector: str) -> str | None:
        element = soup.select_one(selector)
        return element.get_text(strip=True) if element else None

    def _texts(self, soup: BeautifulSoup | Tag, selector: str) -> list[str]:
        return [el.get_text(strip=True) for el in soup.select(selector)]

    def _attr(self, soup: BeautifulSoup | Tag, selector: str, attribute: str) -> str | None:
        element = soup.select_one(selector)
        value = element.get(attribute) if element else None
        if isinstance(value, list):
            return str(value[0]) if value else None
        return str(value) if value is not None else None

    def _attrs(self, soup: BeautifulSoup | Tag, selector: str, attribute: str) -> list[str]:
        result: list[str] = []
        for el in soup.select(selector):
            value = el.get(attribute)
            if isinstance(value, list):
                if value:
                    result.append(str(value[0]))
            elif value is not None:
                result.append(str(value))
        return result
