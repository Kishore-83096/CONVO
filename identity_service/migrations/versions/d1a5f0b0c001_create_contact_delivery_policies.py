"""create contact delivery policies

Revision ID: d1a5f0b0c001
Revises: c53bd1260b44
Create Date: 2026-06-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d1a5f0b0c001"
down_revision = "c53bd1260b44"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contact_delivery_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "is_blocked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "policy_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "owner_id <> target_user_id",
            name="ck_contact_delivery_policy_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id",
            "target_user_id",
            name="uq_contact_delivery_policy_owner_target",
        ),
    )

    op.create_index(
        op.f("ix_contact_delivery_policies_owner_id"),
        "contact_delivery_policies",
        ["owner_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_contact_delivery_policies_target_user_id"),
        "contact_delivery_policies",
        ["target_user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_contact_delivery_policies_target_user_id"),
        table_name="contact_delivery_policies",
    )

    op.drop_index(
        op.f("ix_contact_delivery_policies_owner_id"),
        table_name="contact_delivery_policies",
    )

    op.drop_table("contact_delivery_policies")
    