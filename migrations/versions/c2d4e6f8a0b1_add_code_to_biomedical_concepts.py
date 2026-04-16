"""add code column to biomedical_concepts

Revision ID: c2d4e6f8a0b1
Revises: a1c3e5f7b9d2
Create Date: 2026-04-16 09:15:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c2d4e6f8a0b1"
down_revision = "a1c3e5f7b9d2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("biomedical_concepts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("code", sa.String(50), nullable=True))


def downgrade():
    with op.batch_alter_table("biomedical_concepts", schema=None) as batch_op:
        batch_op.drop_column("code")
