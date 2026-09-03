"""add alignment_jobs table

Revision ID: fb135e287995
Revises: 59f58378e692
Create Date: 2026-09-03 09:52:03.579097

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "fb135e287995"
down_revision = "59f58378e692"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "alignment_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("populate_batches_done", sa.Integer(), nullable=True),
        sa.Column("populate_batches_total", sa.Integer(), nullable=True),
        sa.Column("augment_rows_total", sa.Integer(), nullable=True),
        sa.Column("augment_cdisc_hits", sa.Integer(), nullable=True),
        sa.Column("xlsx_path", sa.String(length=500), nullable=True),
        sa.Column("json_path", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("alignment_jobs")
