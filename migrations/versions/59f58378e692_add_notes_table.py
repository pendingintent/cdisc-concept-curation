"""add notes table

Revision ID: 59f58378e692
Revises: df33730cf8d2
Create Date: 2026-09-01 15:25:05.986387

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "59f58378e692"
down_revision = "df33730cf8d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bc_id", sa.String(length=50), nullable=True),
        sa.Column("vlm_group_id", sa.String(length=100), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("flagged", sa.Boolean(), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.String(length=100), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("(bc_id IS NOT NULL) + (vlm_group_id IS NOT NULL) = 1", name="ck_notes_one_entity"),
        sa.ForeignKeyConstraint(["bc_id"], ["biomedical_concepts.bc_id"], name="fk_notes_bc_id"),
        sa.ForeignKeyConstraint(["vlm_group_id"], ["dataset_specializations.vlm_group_id"], name="fk_notes_vlm_group_id"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("notes")
