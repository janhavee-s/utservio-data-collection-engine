import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import BaseCollector
from app.database.models import SocialPlatform
from app.database.repositories.competitor_social_repository import CompetitorSocialRepository
from app.parsers.strategy_parser import StrategyParser
from app.utilities.url_normalizer import normalize_url


class SocialCollector(BaseCollector):
    def __init__(self) -> None:
        super().__init__()
        self._parser = StrategyParser()

    async def collect(
        self, competitor_id: int, url: str, *, session: AsyncSession, **kwargs: Any
    ) -> dict[str, Any]:
        start_time: float = time.time()

        try:
            result = await self.fetch(url)
            html = result.html

            await self.store_raw(competitor_id, url, html, session)

            parsed = self._parser.parse_for_type(html, url, "social")
            profiles = parsed["social_profiles"]

            social_repo = CompetitorSocialRepository(session)
            profiles_created = 0
            profiles_updated = 0
            for profile in profiles:
                platform_str = profile.get("platform", "")
                try:
                    platform = SocialPlatform(platform_str)
                except ValueError:
                    continue

                profile_url = normalize_url(profile.get("profile_url", ""), base_url=url)
                username = profile.get("username")

                existing = await social_repo.get_by_platform(competitor_id, platform)
                await social_repo.upsert(
                    competitor_id=competitor_id,
                    platform=platform,
                    profile_url=profile_url,
                    username=username,
                )
                if existing:
                    profiles_updated += 1
                else:
                    profiles_created += 1

            return {
                "status": "success",
                "profiles_found": len(profiles),
                "profiles_created": profiles_created,
                "profiles_updated": profiles_updated,
                "elapsed_seconds": self._elapsed(start_time),
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "profiles_found": 0,
                "profiles_created": 0,
                "profiles_updated": 0,
                "elapsed_seconds": self._elapsed(start_time),
            }
