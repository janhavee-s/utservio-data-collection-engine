"""Initial schema - all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-07-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enums
    sa.Enum("hourly", "daily", "weekly", name="collection_frequency_enum").create(
        op.get_bind(), checkfirst=True
    )
    sa.Enum("success", "failed", "partial", name="collection_status_enum").create(
        op.get_bind(), checkfirst=True
    )
    sa.Enum(
        "linkedin", "facebook", "instagram", "twitter", "youtube", "pinterest", "threads",
        name="social_platform_enum",
    ).create(op.get_bind(), checkfirst=True)

    # competitors
    op.create_table(
        "competitors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("website_url", sa.String(2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "collection_frequency",
            sa.Enum("hourly", "daily", "weekly", name="collection_frequency_enum"),
            nullable=False,
            server_default="daily",
        ),
        sa.Column("modules", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_competitor_collection_frequency", "competitors", ["collection_frequency"])

    # competitor_sources
    op.create_table(
        "competitor_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("competitor_id", sa.Integer(), sa.ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("page_type", sa.String(100), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("competitor_id", "url", name="uq_competitor_source_url"),
    )
    op.create_index("ix_competitor_source_competitor_id", "competitor_sources", ["competitor_id"])
    op.create_index("ix_competitor_source_url", "competitor_sources", ["url"])

    # competitor_pages
    op.create_table(
        "competitor_pages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("competitor_id", sa.Integer(), sa.ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("competitor_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "collection_status",
            sa.Enum("success", "failed", "partial", name="collection_status_enum"),
            nullable=False,
            server_default="success",
        ),
        sa.UniqueConstraint("competitor_id", "source_id", name="uq_competitor_page_source"),
    )
    op.create_index("ix_competitor_page_competitor_id", "competitor_pages", ["competitor_id"])
    op.create_index("ix_competitor_page_source_id", "competitor_pages", ["source_id"])

    # competitor_services
    op.create_table(
        "competitor_services",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("competitor_id", sa.Integer(), sa.ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_category", sa.String(255), nullable=True),
        sa.Column("service_name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("estimated_duration", sa.String(100), nullable=True),
        sa.Column("starting_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("available_add_ons", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("membership_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("offers", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("discounts", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_competitor_service_competitor_id", "competitor_services", ["competitor_id"])
    op.create_index("ix_competitor_service_content_hash", "competitor_services", ["content_hash"])

    # competitor_pricing
    op.create_table(
        "competitor_pricing",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("competitor_id", sa.Integer(), sa.ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_name", sa.String(500), nullable=False),
        sa.Column("category", sa.String(255), nullable=True),
        sa.Column("base_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("promotional_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("discount", sa.Numeric(10, 2), nullable=True),
        sa.Column("membership_pricing", sa.JSON(), nullable=True),
        sa.Column("subscription_plans", sa.JSON(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_competitor_pricing_competitor_id", "competitor_pricing", ["competitor_id"])
    op.create_index("ix_competitor_pricing_content_hash", "competitor_pricing", ["content_hash"])

    # competitor_content
    op.create_table(
        "competitor_content",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("competitor_id", sa.Integer(), sa.ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("publish_date", sa.Date(), nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("competitor_id", "url", name="uq_competitor_content_url"),
    )
    op.create_index("ix_competitor_content_competitor_id", "competitor_content", ["competitor_id"])
    op.create_index("ix_competitor_content_url", "competitor_content", ["url"])
    op.create_index("ix_competitor_content_content_hash", "competitor_content", ["content_hash"])

    # competitor_social
    op.create_table(
        "competitor_social",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("competitor_id", sa.Integer(), sa.ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("linkedin", "facebook", "instagram", "twitter", "youtube", "pinterest", "threads", name="social_platform_enum"),
            nullable=False,
        ),
        sa.Column("profile_url", sa.String(2048), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("competitor_id", "platform", name="uq_competitor_social_platform"),
    )
    op.create_index("ix_competitor_social_competitor_id", "competitor_social", ["competitor_id"])

    # collection_logs
    op.create_table(
        "collection_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("competitor_id", sa.Integer(), sa.ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("duration_seconds", sa.Numeric(10, 2), nullable=True),
        sa.Column("records_collected", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("errors", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_collection_log_competitor_id", "collection_logs", ["competitor_id"])
    op.create_index("ix_collection_log_start_time", "collection_logs", ["start_time"])

    # competitor_company_info
    op.create_table(
        "competitor_company_info",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("competitor_id", sa.Integer(), sa.ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("logo_url", sa.String(2048), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("headquarters", sa.String(500), nullable=True),
        sa.Column("operating_countries", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("operating_cities", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("social_links", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("competitor_id", name="uq_competitor_company_info"),
    )
    op.create_index("ix_competitor_company_info_competitor_id", "competitor_company_info", ["competitor_id"])

    # raw_storage
    op.create_table(
        "raw_storage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("competitor_id", sa.Integer(), sa.ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "collection_status",
            sa.Enum("success", "failed", "partial", name="collection_status_enum"),
            nullable=False,
            server_default="success",
        ),
        sa.UniqueConstraint("competitor_id", "source_url", name="uq_raw_storage_competitor_url"),
    )
    op.create_index("ix_raw_storage_competitor_id", "raw_storage", ["competitor_id"])
    op.create_index("ix_raw_storage_source_url", "raw_storage", ["source_url"])
    op.create_index("ix_raw_storage_content_hash", "raw_storage", ["content_hash"])


def downgrade() -> None:
    op.drop_table("raw_storage")
    op.drop_table("competitor_company_info")
    op.drop_table("collection_logs")
    op.drop_table("competitor_social")
    op.drop_table("competitor_content")
    op.drop_table("competitor_pricing")
    op.drop_table("competitor_services")
    op.drop_table("competitor_pages")
    op.drop_table("competitor_sources")
    op.drop_table("competitors")
    sa.Enum(name="social_platform_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="collection_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="collection_frequency_enum").drop(op.get_bind(), checkfirst=True)
