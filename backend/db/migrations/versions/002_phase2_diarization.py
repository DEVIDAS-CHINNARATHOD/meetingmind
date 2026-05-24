"""
db/migrations/versions/002_phase2_diarization.py
Phase 2: no new tables needed — speaker data flows into existing
TranscriptSegment.speaker_name and Participant columns created in Phase 1.

This migration is a placeholder/verification that the schema is ready.
Run: alembic upgrade head
"""
from alembic import op
import sqlalchemy as sa

revision = "002_phase2"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TranscriptSegment.speaker_name already exists from Phase 1 migration.
    # We just ensure the index on speaker_label exists for fast filtering.
    op.create_index(
        "ix_transcript_segments_speaker_label",
        "transcript_segments",
        ["speaker_label"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_participants_speaker_label",
        "participants",
        ["speaker_label"],
        if_not_exists=True,
    )
    # Add workspace-scoped index on meetings for analytics queries
    op.create_index(
        "ix_meetings_workspace_status",
        "meetings",
        ["workspace_id", "status"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_transcript_segments_speaker_label", "transcript_segments")
    op.drop_index("ix_participants_speaker_label", "participants")
    op.drop_index("ix_meetings_workspace_status", "meetings")
