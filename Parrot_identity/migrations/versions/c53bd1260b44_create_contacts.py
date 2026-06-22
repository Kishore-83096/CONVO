"""create contacts

Revision ID: c53bd1260b44
Revises: 6da61ddeca45
Create Date: 2026-06-22 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c53bd1260b44"
down_revision = "6da61ddeca45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("contact_user_id", sa.Integer(), nullable=False),
        sa.Column("saved_name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "owner_id <> contact_user_id",
            name="ck_contacts_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["contact_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id",
            "contact_user_id",
            name="uq_contacts_owner_contact_user",
        ),
    )
    with op.batch_alter_table("contacts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_contacts_contact_user_id"),
            ["contact_user_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_contacts_owner_id"),
            ["owner_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("contacts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_contacts_owner_id"))
        batch_op.drop_index(batch_op.f("ix_contacts_contact_user_id"))

    op.drop_table("contacts")
