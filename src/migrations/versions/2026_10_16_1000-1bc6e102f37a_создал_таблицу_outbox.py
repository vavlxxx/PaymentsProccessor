"""создал таблицу outbox

Revision ID: 1bc6e102f37a
Revises: 0ab5f001e26f
Create Date: 2026-10-16 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1bc6e102f37a"
down_revision: str | Sequence[str] | None = "0ab5f001e26f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "outbox",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "success",
                "failed",
                name="outbox_status_enum",
                native_enum=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox")),
    )
    op.create_index(
        op.f("ix_outbox_event_id"),
        "outbox",
        ["event_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_outbox_topic"),
        "outbox",
        ["topic"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbox_status"),
        "outbox",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_outbox_status"), table_name="outbox")
    op.drop_index(op.f("ix_outbox_topic"), table_name="outbox")
    op.drop_index(op.f("ix_outbox_event_id"), table_name="outbox")
    op.drop_table("outbox")
