import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

import structlog

from app.configuration.settings import get_settings
from app.database.connection import db_manager
from app.database.models import CollectionFrequency, CollectionLog
from app.database.repositories.competitor_repository import CompetitorRepository
from app.services.collection_service import collection_service

logger = structlog.get_logger(__name__)


class CollectionScheduler:
    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._interval_seconds: int = 60

    async def start(self) -> None:
        if self._running:
            logger.warning("scheduler_already_running")
            return

        settings = get_settings()
        if not settings.scheduler.enabled:
            logger.info("scheduler_disabled")
            return

        self._running = True
        self._interval_seconds = settings.scheduler.check_interval_seconds
        self._task = asyncio.create_task(self._run_loop())
        logger.info("scheduler_started", interval=self._interval_seconds)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("scheduler_stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self._check_and_collect()
            except Exception:
                logger.exception("scheduler_check_failed")
            await asyncio.sleep(self._interval_seconds)

    async def _check_and_collect(self) -> None:
        try:
            async with db_manager.session() as session:
                comp_repo = CompetitorRepository(session)

                now = datetime.now(UTC)
                for freq in CollectionFrequency:
                    competitors = await comp_repo.get_by_frequency(freq)
                    for comp in competitors:
                        if not comp.enabled:
                            continue

                        last_log = await self._get_last_collection_log(session, comp.id)
                        if last_log and not self._should_collect(last_log, freq, now):
                            logger.debug(
                                "skipping_competitor_not_due",
                                competitor_id=comp.id,
                                name=comp.name,
                                frequency=freq.value,
                            )
                            continue

                        logger.info(
                            "scheduling_collection",
                            competitor_id=comp.id,
                            name=comp.name,
                            frequency=freq.value,
                        )
                        try:
                            await collection_service.collect_competitor(comp.id)
                        except Exception:
                            logger.exception(
                                "scheduled_collection_failed",
                                competitor_id=comp.id,
                            )
        except Exception:
            logger.exception("scheduler_check_cycle_failed")

    async def _get_last_collection_log(self, session: Any, competitor_id: int) -> Any:
        from app.database.repositories.collection_log_repository import CollectionLogRepository

        log_repo = CollectionLogRepository(session)
        return await log_repo.get_latest_by_competitor(competitor_id)

    def _should_collect(
        self, last_log: CollectionLog | None, frequency: CollectionFrequency, now: datetime
    ) -> bool:
        if not last_log or not last_log.start_time:
            return True

        elapsed = (now - last_log.start_time).total_seconds()
        return elapsed >= frequency.interval_seconds

    @property
    def is_running(self) -> bool:
        return self._running


scheduler = CollectionScheduler()
