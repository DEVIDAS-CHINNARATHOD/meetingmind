"""
models/orm.py
SQLAlchemy ORM models — single source of truth for the DB schema.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, func, BigInteger,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


class WorkspacePlan(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class MeetingStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"


class MeetingSource(str, enum.Enum):
    UPLOAD = "upload"
    ZOOM = "zoom"
    GOOGLE_MEET = "google_meet"
    TEAMS = "teams"


class ReportType(str, enum.Enum):
    MOM = "mom"
    TRANSCRIPT = "transcript"
    ANALYTICS = "analytics"
    SUMMARY = "summary"


# ═══════════════════════════════════════════════════════════════
# Mixins
# ═══════════════════════════════════════════════════════════════

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════

class Workspace(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    plan: Mapped[WorkspacePlan] = mapped_column(
        Enum(WorkspacePlan), default=WorkspacePlan.FREE, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Limits per plan
    monthly_meeting_limit: Mapped[int] = mapped_column(Integer, default=5)
    storage_limit_gb: Mapped[int] = mapped_column(Integer, default=5)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="workspace")
    meetings: Mapped[list["Meeting"]] = relationship("Meeting", back_populates="workspace")


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.VIEWER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="users")
    meetings: Mapped[list["Meeting"]] = relationship("Meeting", back_populates="creator")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(UUIDMixin, Base):
    __tablename__ = "refresh_tokens"

    token: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


class Meeting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "meetings"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus), default=MeetingStatus.PENDING, nullable=False, index=True
    )
    source: Mapped[MeetingSource] = mapped_column(
        Enum(MeetingSource), default=MeetingSource.UPLOAD, nullable=False
    )

    # File info
    original_filename: Mapped[str | None] = mapped_column(String(255))
    file_key: Mapped[str | None] = mapped_column(String(500))    # S3/local key
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    audio_extracted_key: Mapped[str | None] = mapped_column(String(500))

    # AI outputs
    transcript: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    mom: Mapped[str | None] = mapped_column(Text)              # Minutes of Meeting (markdown)
    key_decisions: Mapped[list | None] = mapped_column(JSONB)  # [{decision, timestamp}]
    topics: Mapped[list | None] = mapped_column(JSONB)         # [str]

    # Processing metadata
    language: Mapped[str | None] = mapped_column(String(10))
    word_count: Mapped[int | None] = mapped_column(Integer)
    processing_error: Mapped[str | None] = mapped_column(Text)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))

    # External meeting IDs (Phase 4)
    external_meeting_id: Mapped[str | None] = mapped_column(String(255))
    external_join_url: Mapped[str | None] = mapped_column(String(500))

    # Relations
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="meetings")
    creator: Mapped["User"] = relationship("User", back_populates="meetings")
    participants: Mapped[list["Participant"]] = relationship(
        "Participant", back_populates="meeting", cascade="all, delete-orphan"
    )
    action_items: Mapped[list["ActionItem"]] = relationship(
        "ActionItem", back_populates="meeting", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report", back_populates="meeting", cascade="all, delete-orphan"
    )
    transcript_segments: Mapped[list["TranscriptSegment"]] = relationship(
        "TranscriptSegment", back_populates="meeting", cascade="all, delete-orphan"
    )


class Participant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "participants"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    speaker_label: Mapped[str | None] = mapped_column(String(20))   # SPEAKER_00, SPEAKER_01...
    email: Mapped[str | None] = mapped_column(String(255))
    talk_time_seconds: Mapped[float | None] = mapped_column(Float)
    word_count: Mapped[int | None] = mapped_column(Integer)
    face_embedding: Mapped[list | None] = mapped_column(JSONB)        # Phase 3

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="participants")


class TranscriptSegment(UUIDMixin, Base):
    """Individual diarized transcript segments with timestamps."""
    __tablename__ = "transcript_segments"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    speaker_label: Mapped[str | None] = mapped_column(String(20))
    speaker_name: Mapped[str | None] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)  # seconds
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="transcript_segments")


class ActionItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "action_items"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    task: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(120))
    deadline: Mapped[str | None] = mapped_column(String(50))         # flexible format
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[str | None] = mapped_column(String(20))         # low | medium | high

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="action_items")


class Report(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType), nullable=False)
    file_key: Mapped[str | None] = mapped_column(String(500))   # storage path/key
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    format: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf | docx | txt | csv
    download_count: Mapped[int] = mapped_column(Integer, default=0)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="reports")
