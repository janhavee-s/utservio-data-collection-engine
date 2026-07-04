from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verify_api_key
from app.database.connection import db_manager
from app.database.models import (
    CompetitorCompanyInfo,
    CompetitorContent,
    CompetitorPricing,
    CompetitorService,
    CompetitorSocial,
)

router = APIRouter(tags=["data"])


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with db_manager.session() as session:
        yield session


@router.get("/competitors/{competitor_id}/services")
async def get_services(
    competitor_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _api_key: str = Security(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Get services for a competitor."""
    stmt = (
        select(CompetitorService)
        .where(CompetitorService.competitor_id == competitor_id)
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    services = result.scalars().all()

    count_stmt = (
        select(func.count())
        .select_from(CompetitorService)
        .where(CompetitorService.competitor_id == competitor_id)
    )
    total = (await session.execute(count_stmt)).scalar() or 0

    return {
        "competitor_id": competitor_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "services": [
            {
                "id": s.id,
                "service_name": s.service_name,
                "service_category": s.service_category,
                "description": s.description,
                "starting_price": float(s.starting_price) if s.starting_price else None,
                "currency": s.currency,
                "estimated_duration": s.estimated_duration,
                "collected_at": s.collected_at.isoformat() if s.collected_at else None,
            }
            for s in services
        ],
    }


@router.get("/competitors/{competitor_id}/pricing")
async def get_pricing(
    competitor_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _api_key: str = Security(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Get pricing for a competitor."""
    stmt = (
        select(CompetitorPricing)
        .where(CompetitorPricing.competitor_id == competitor_id)
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    pricing = result.scalars().all()

    count_stmt = (
        select(func.count())
        .select_from(CompetitorPricing)
        .where(CompetitorPricing.competitor_id == competitor_id)
    )
    total = (await session.execute(count_stmt)).scalar() or 0

    return {
        "competitor_id": competitor_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "pricing": [
            {
                "id": p.id,
                "service_name": p.service_name,
                "category": p.category,
                "base_price": float(p.base_price) if p.base_price else None,
                "promotional_price": float(p.promotional_price) if p.promotional_price else None,
                "currency": p.currency,
                "discount": float(p.discount) if p.discount else None,
                "collected_at": p.collected_at.isoformat() if p.collected_at else None,
            }
            for p in pricing
        ],
    }


@router.get("/competitors/{competitor_id}/social")
async def get_social(
    competitor_id: int,
    _api_key: str = Security(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Get social profiles for a competitor."""
    stmt = select(CompetitorSocial).where(
        CompetitorSocial.competitor_id == competitor_id
    )
    result = await session.execute(stmt)
    social = result.scalars().all()

    return {
        "competitor_id": competitor_id,
        "social_profiles": [
            {
                "id": s.id,
                "platform": s.platform,
                "profile_url": s.profile_url,
                "username": s.username,
                "collected_at": s.collected_at.isoformat() if s.collected_at else None,
            }
            for s in social
        ],
    }


@router.get("/competitors/{competitor_id}/company")
async def get_company(
    competitor_id: int,
    _api_key: str = Security(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Get company info for a competitor."""
    stmt = select(CompetitorCompanyInfo).where(
        CompetitorCompanyInfo.competitor_id == competitor_id
    )
    result = await session.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(status_code=404, detail="Company info not found")

    return {
        "competitor_id": competitor_id,
        "company": {
            "id": company.id,
            "logo_url": company.logo_url,
            "description": company.description,
            "industry": company.industry,
            "headquarters": company.headquarters,
            "operating_countries": company.operating_countries,
            "operating_cities": company.operating_cities,
            "contact_email": company.contact_email,
            "contact_phone": company.contact_phone,
            "social_links": company.social_links,
            "collected_at": company.collected_at.isoformat() if company.collected_at else None,
        },
    }


@router.get("/competitors/{competitor_id}/content")
async def get_content(
    competitor_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _api_key: str = Security(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Get content for a competitor."""
    stmt = (
        select(CompetitorContent)
        .where(CompetitorContent.competitor_id == competitor_id)
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    content = result.scalars().all()

    count_stmt = (
        select(func.count())
        .select_from(CompetitorContent)
        .where(CompetitorContent.competitor_id == competitor_id)
    )
    total = (await session.execute(count_stmt)).scalar() or 0

    return {
        "competitor_id": competitor_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "content": [
            {
                "id": c.id,
                "title": c.title,
                "author": c.author,
                "url": c.url,
                "summary": c.summary,
                "content_type": c.content_type,
                "publish_date": c.publish_date.isoformat() if c.publish_date else None,
                "collected_at": c.collected_at.isoformat() if c.collected_at else None,
            }
            for c in content
        ],
    }


@router.get("/competitors/{competitor_id}/overview")
async def get_overview(
    competitor_id: int,
    _api_key: str = Security(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Get overview of all data for a competitor."""
    services_count = (
        await session.execute(
            select(func.count())
            .select_from(CompetitorService)
            .where(CompetitorService.competitor_id == competitor_id)
        )
    ).scalar() or 0

    pricing_count = (
        await session.execute(
            select(func.count())
            .select_from(CompetitorPricing)
            .where(CompetitorPricing.competitor_id == competitor_id)
        )
    ).scalar() or 0

    social_count = (
        await session.execute(
            select(func.count())
            .select_from(CompetitorSocial)
            .where(CompetitorSocial.competitor_id == competitor_id)
        )
    ).scalar() or 0

    content_count = (
        await session.execute(
            select(func.count())
            .select_from(CompetitorContent)
            .where(CompetitorContent.competitor_id == competitor_id)
        )
    ).scalar() or 0

    company = (
        await session.execute(
            select(CompetitorCompanyInfo).where(
                CompetitorCompanyInfo.competitor_id == competitor_id
            )
        )
    ).scalar_one_or_none()

    return {
        "competitor_id": competitor_id,
        "services_count": services_count,
        "pricing_count": pricing_count,
        "social_count": social_count,
        "content_count": content_count,
        "has_company_info": company is not None,
    }
