"""Add missing unique constraints for ON CONFLICT upsert

Revision ID: 002_add_unique_constraints
Revises: 001_initial
Create Date: 2026-07-03 00:00:01.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002_add_unique_constraints"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unique constraint for competitor_services ON CONFLICT (competitor_id, content_hash)
    op.create_unique_constraint(
        "uq_competitor_service_content_hash",
        "competitor_services",
        ["competitor_id", "content_hash"],
    )

    # Add unique constraint for competitor_pricing ON CONFLICT (competitor_id, content_hash)
    op.create_unique_constraint(
        "uq_competitor_pricing_content_hash",
        "competitor_pricing",
        ["competitor_id", "content_hash"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_competitor_service_content_hash", "competitor_services", type_="unique")
    op.drop_constraint("uq_competitor_pricing_content_hash", "competitor_pricing", type_="unique")
