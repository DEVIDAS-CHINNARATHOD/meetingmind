"""
db/migrations/versions/004_phase4_bots.py
Phase 4: Add external_join_url and bot-related columns to meetings.
(external_meeting_id + celery_task_id already in Phase 1 models)
Run: alembic upgrade head
"""
from alembic import op
import sqlalchemy as sa

revision = "004_phase4"
down_revision = "003_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # external_join_url might not exist yet (added in models but
    # migration must be explicit)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("meetings")]
    if "external_join_url" not in columns:
        op.add_column(
            "meetings",
            sa.Column("external_join_url", sa.String(500), nullable=True),
        )
    # Index for webhook lookups by external Zoom meeting ID
    op.create_index(
        "ix_meetings_external_meeting_id",
        "meetings",
        ["external_meeting_id"],
        if_not_exists=True,
    )
    # Index for fast source-based filtering (Zoom vs Meet vs Upload)
    op.create_index(
        "ix_meetings_source",
        "meetings",
        ["source"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_column("meetings", "external_join_url")
    op.drop_index("ix_meetings_external_meeting_id", "meetings")
    op.drop_index("ix_meetings_source", "meetings")
