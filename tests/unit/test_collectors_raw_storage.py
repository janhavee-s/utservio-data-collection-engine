from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.collectors.company import CompanyCollector
from app.collectors.content import ContentCollector
from app.collectors.fetcher import FetchResult
from app.collectors.pricing import PricingCollector
from app.collectors.service import ServiceCollector
from app.collectors.social import SocialCollector


class TestCompanyCollectorRawStorage:
    @pytest.mark.asyncio
    async def test_stores_raw_html(self) -> None:
        collector = CompanyCollector()
        mock_result = FetchResult(
            html="<html><body><h1>Company</h1></body></html>",
            url="https://example.com",
            method="httpx",
            status_code=200,
            content_length=40,
        )

        with (
            patch.object(collector, "fetch", new_callable=AsyncMock, return_value=mock_result),
            patch.object(collector, "store_raw", new_callable=AsyncMock) as mock_store,
            patch("app.collectors.company.CompetitorCompanyInfoRepository") as mock_repo_cls,
        ):
            mock_repo = AsyncMock()
            mock_repo.upsert = AsyncMock(return_value=(MagicMock(), True))
            mock_repo_cls.return_value = mock_repo

            session = MagicMock()
            result = await collector.collect(1, "https://example.com", session=session)

            mock_store.assert_called_once_with(1, "https://example.com", mock_result.html, session)
            assert result["status"] == "success"


class TestServiceCollectorRawStorage:
    @pytest.mark.asyncio
    async def test_stores_raw_html(self) -> None:
        collector = ServiceCollector()
        mock_result = FetchResult(
            html="<html><body>Services</body></html>",
            url="https://example.com",
            method="httpx",
            status_code=200,
            content_length=35,
        )

        with (
            patch.object(collector, "fetch", new_callable=AsyncMock, return_value=mock_result),
            patch.object(collector, "store_raw", new_callable=AsyncMock) as mock_store,
            patch("app.collectors.service.CompetitorServiceRepository") as mock_repo_cls,
        ):
            mock_repo = AsyncMock()
            mock_repo.delete_by_competitor = AsyncMock()
            mock_repo.create = AsyncMock()
            mock_repo_cls.return_value = mock_repo

            session = MagicMock()
            result = await collector.collect(1, "https://example.com", session=session)

            mock_store.assert_called_once_with(1, "https://example.com", mock_result.html, session)
            assert result["status"] == "success"


class TestPricingCollectorRawStorage:
    @pytest.mark.asyncio
    async def test_stores_raw_html(self) -> None:
        collector = PricingCollector()
        mock_result = FetchResult(
            html="<html><body>Pricing</body></html>",
            url="https://example.com",
            method="httpx",
            status_code=200,
            content_length=35,
        )

        with (
            patch("app.collectors.fetcher.HybridFetcher") as mock_fetcher_cls,
            patch.object(collector, "store_raw", new_callable=AsyncMock) as mock_store,
            patch("app.collectors.pricing.CompetitorPricingRepository") as mock_repo_cls,
        ):
            mock_fetcher = AsyncMock()
            mock_fetcher._fetch_dynamic_with_city_selection = AsyncMock(
                return_value=(mock_result, [])
            )
            mock_fetcher_cls.return_value = mock_fetcher
            
            mock_repo = AsyncMock()
            mock_repo.delete_by_competitor = AsyncMock()
            mock_repo.create = AsyncMock()
            mock_repo_cls.return_value = mock_repo

            session = MagicMock()
            result = await collector.collect(1, "https://example.com", session=session)

            mock_store.assert_called_once_with(1, "https://example.com", mock_result.html, session)
            assert result["status"] == "success"


class TestContentCollectorRawStorage:
    @pytest.mark.asyncio
    async def test_stores_raw_html(self) -> None:
        collector = ContentCollector()
        mock_result = FetchResult(
            html="<html><body>Content</body></html>",
            url="https://example.com",
            method="httpx",
            status_code=200,
            content_length=35,
        )

        with (
            patch.object(collector, "fetch", new_callable=AsyncMock, return_value=mock_result),
            patch.object(collector, "store_raw", new_callable=AsyncMock) as mock_store,
            patch("app.collectors.content.CompetitorContentRepository") as mock_repo_cls,
        ):
            mock_repo = AsyncMock()
            mock_repo.get_by_url = AsyncMock(return_value=None)
            mock_repo.create = AsyncMock()
            mock_repo_cls.return_value = mock_repo

            session = MagicMock()
            result = await collector.collect(1, "https://example.com", session=session)

            mock_store.assert_called_once_with(1, "https://example.com", mock_result.html, session)
            assert result["status"] == "success"


class TestSocialCollectorRawStorage:
    @pytest.mark.asyncio
    async def test_stores_raw_html(self) -> None:
        collector = SocialCollector()
        mock_result = FetchResult(
            html="<html><body>Social</body></html>",
            url="https://example.com",
            method="httpx",
            status_code=200,
            content_length=35,
        )

        with (
            patch.object(collector, "fetch", new_callable=AsyncMock, return_value=mock_result),
            patch.object(collector, "store_raw", new_callable=AsyncMock) as mock_store,
            patch("app.collectors.social.CompetitorSocialRepository") as mock_repo_cls,
        ):
            mock_repo = AsyncMock()
            mock_repo.upsert = AsyncMock()
            mock_repo_cls.return_value = mock_repo

            session = MagicMock()
            result = await collector.collect(1, "https://example.com", session=session)

            mock_store.assert_called_once_with(1, "https://example.com", mock_result.html, session)
            assert result["status"] == "success"
