from typing import Annotated, Any

from fastapi import APIRouter, Depends, Security
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verify_api_key
from app.api.dependencies import get_session
from app.database.models import CollectionLog, Competitor

router = APIRouter(tags=["health"])


@router.get("/status")
async def status(
    session: AsyncSession = Depends(get_session),
    _auth: str = Security(verify_api_key),
) -> dict[str, Any]:
    competitor_count = await session.scalar(select(func.count()).select_from(Competitor))
    log_count = await session.scalar(select(func.count()).select_from(CollectionLog))
    return {
        "status": "running",
        "competitors": competitor_count or 0,
        "collection_logs": log_count or 0,
    }


@router.get("/logs")
async def get_logs(
    limit: Annotated[int, Field(ge=1, le=1000)] = 50,
    session: AsyncSession = Depends(get_session),
    _auth: str = Security(verify_api_key),
) -> list[dict[str, Any]]:
    stmt = select(CollectionLog).order_by(CollectionLog.id.desc()).limit(limit)
    result = await session.execute(stmt)
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "competitor_id": log.competitor_id,
            "start_time": log.start_time.isoformat() if log.start_time else None,
            "end_time": log.end_time.isoformat() if log.end_time else None,
            "success": log.success,
            "duration_seconds": float(log.duration_seconds) if log.duration_seconds else None,
            "records_collected": log.records_collected,
            "errors": log.errors or [],
            "retry_count": log.retry_count,
        }
        for log in logs
    ]
