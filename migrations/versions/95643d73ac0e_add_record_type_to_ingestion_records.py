"""add record_type to ingestion_records

Revision ID: 95643d73ac0e
Revises: 51d4a009d291
Create Date: 2026-08-28 15:16:03.771535

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "95643d73ac0e"
down_revision = "51d4a009d291"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ingestion_records", schema=None) as batch_op:
        batch_op.add_column(sa.Column("record_type", sa.String(length=20), nullable=False, server_default="bc"))


def downgrade():
    with op.batch_alter_table("ingestion_records", schema=None) as batch_op:
        batch_op.drop_column("record_type")
