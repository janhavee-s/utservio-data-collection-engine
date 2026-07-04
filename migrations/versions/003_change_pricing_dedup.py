"""Change pricing deduplication from content_hash to service_name.

Revision ID: 003
Revises: 002
Create Date: 2026-07-02
"""

from alembic import op
import sqlalchemy as sa


revision = "003_change_pricing_dedup"
down_revision = "002_add_unique_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create unique constraint on (competitor_id, service_name) for pricing
    op.create_unique_constraint(
        "uq_competitor_pricing_service",
        "competitor_pricing",
        ["competitor_id", "service_name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_competitor_pricing_service", "competitor_pricing", type_="unique")
