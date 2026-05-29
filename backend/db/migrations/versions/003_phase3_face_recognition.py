"""
db/migrations/versions/003_phase3_face_recognition.py
Phase 3: Adds face_embedding storage to Participant and
a dedicated face_recognition_results JSONB column to Meeting.

Run: alembic upgrade head
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003_phase3"
down_revision = "002_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # face_embedding already defined in models as JSONB — just add index
    # Add face_recognition_results column to meetings if it doesn't exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("meetings")]
    if "face_recognition_results" not in columns:
        op.add_column(
            "meetings",
            sa.Column("face_recognition_results", JSONB, nullable=True),
        )

    # Index on participant speaker_label for fast join
    op.create_index(
        "ix_participants_meeting_speaker",
        "participants",
        ["meeting_id", "speaker_label"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_column("meetings", "face_recognition_results")
    op.drop_index("ix_participants_meeting_speaker", "participants")
