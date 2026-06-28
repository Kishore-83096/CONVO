"""add ghost to contact delivery policies

Revision ID: e2b6f0b0c002
Revises: d1a5f0b0c001
Create Date: 2026-06-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e2b6f0b0c002"
down_revision = "d1a5f0b0c001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "contact_delivery_policies",
        sa.Column(
            "ghost_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "contact_delivery_policies",
        sa.Column(
            "ghost_permanent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "contact_delivery_policies",
        sa.Column(
            "ghost_duration_option",
            sa.String(length=20),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(
        "contact_delivery_policies",
        "ghost_duration_option",
    )

    op.drop_column(
        "contact_delivery_policies",
        "ghost_permanent",
    )

    op.drop_column(
        "contact_delivery_policies",
        "ghost_until",
    )