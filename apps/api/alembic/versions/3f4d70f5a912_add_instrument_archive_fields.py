"""add instrument archive fields

Revision ID: 3f4d70f5a912
Revises: 7b469545c8aa
Create Date: 2026-10-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "3f4d70f5a912"
down_revision: Union[str, None] = "7b469545c8aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "archive_reason",
                sa.String(length=200),
                nullable=False,
                server_default="",
            )
        )
        batch_op.create_index(
            batch_op.f("ix_instruments_archived_at"),
            ["archived_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_instruments_archived_at"))
        batch_op.drop_column("archive_reason")
        batch_op.drop_column("archived_at")
