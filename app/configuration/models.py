from enum import StrEnum

from pydantic import BaseModel, Field

from app.database.models import CollectionFrequency


class CollectionModule(StrEnum):
    DISCOVERY = "discovery"
    COMPANY = "company"
    SERVICES = "services"
    PRICING = "pricing"
    CONTENT = "content"
    SOCIAL = "social"


class CompetitorConfig(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    website_url: str = Field(..., pattern=r"^https?://")
    enabled: bool = Field(default=True)
    collection_frequency: CollectionFrequency = Field(default=CollectionFrequency.DAILY)
    modules: list[CollectionModule] = Field(default_factory=lambda: list(CollectionModule))
    tags: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=1000)


class CompetitorsFile(BaseModel):
    competitors: list[CompetitorConfig] = Field(default_factory=list)
