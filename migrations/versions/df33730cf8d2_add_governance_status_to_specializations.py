"""add governance status to specializations

Revision ID: df33730cf8d2
Revises: 95643d73ac0e
Create Date: 2026-08-31 13:03:31.303332

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "df33730cf8d2"
down_revision = "95643d73ac0e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("dataset_specializations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=50), nullable=False, server_default="provisional"))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.execute("UPDATE dataset_specializations SET updated_at = created_at")

    with op.batch_alter_table("governance_records", schema=None) as batch_op:
        batch_op.add_column(sa.Column("vlm_group_id", sa.String(length=100), nullable=True))
        batch_op.alter_column("bc_id", existing_type=sa.VARCHAR(length=50), nullable=True)
        batch_op.create_foreign_key("fk_governance_records_vlm_group_id", "dataset_specializations", ["vlm_group_id"], ["vlm_group_id"])
        batch_op.create_check_constraint(
            "ck_governance_records_one_entity",
            "(bc_id IS NOT NULL) + (vlm_group_id IS NOT NULL) = 1",
        )


def downgrade():
    with op.batch_alter_table("governance_records", schema=None) as batch_op:
        batch_op.drop_constraint("ck_governance_records_one_entity", type_="check")
        batch_op.drop_constraint("fk_governance_records_vlm_group_id", type_="foreignkey")
        batch_op.alter_column("bc_id", existing_type=sa.VARCHAR(length=50), nullable=False)
        batch_op.drop_column("vlm_group_id")

    with op.batch_alter_table("dataset_specializations", schema=None) as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("status")
