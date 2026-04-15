"""rename code to loinc_code in biomedical_concepts

Revision ID: a1c3e5f7b9d2
Revises: b9ee22a174fe
Create Date: 2026-04-15 14:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1c3e5f7b9d2"
down_revision = "b9ee22a174fe"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("biomedical_concepts", schema=None) as batch_op:
        batch_op.alter_column("code", new_column_name="loinc_code", existing_type=sa.String(50), existing_nullable=True)


def downgrade():
    with op.batch_alter_table("biomedical_concepts", schema=None) as batch_op:
        batch_op.alter_column("loinc_code", new_column_name="code", existing_type=sa.String(50), existing_nullable=True)
