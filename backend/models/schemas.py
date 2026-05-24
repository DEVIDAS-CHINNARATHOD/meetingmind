"""
models/schemas.py
Pydantic v2 request/response schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ═══════════════════════════════════════════════════════════════
# Base
# ═══════════════════════════════════════════════════════════════

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════

class WorkspaceCreate(BaseSchema):
    name: str = Field(..., min_length=2, max_length=120)
    slug: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")


class RegisterRequest(BaseSchema):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    workspace: WorkspaceCreate


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str


class TokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int   # seconds


class RefreshRequest(BaseSchema):
    refresh_token: str


class UserOut(BaseSchema):
    id: uuid.UUID
    name: str
    email: str
    role: str
    is_active: bool
    is_verified: bool
    avatar_url: str | None
    workspace_id: uuid.UUID
    created_at: datetime


# ═══════════════════════════════════════════════════════════════
# Meeting
# ═══════════════════════════════════════════════════════════════

class MeetingCreate(BaseSchema):
    title: str = Field(..., min_length=1, max_length=255)


class MeetingUpdate(BaseSchema):
    title: str | None = Field(None, max_length=255)
    status: str | None = None


class ParticipantOut(BaseSchema):
    id: uuid.UUID
    name: str
    speaker_label: str | None
    talk_time_seconds: float | None
    word_count: int | None


class TranscriptSegmentOut(BaseSchema):
    id: uuid.UUID
    speaker_label: str | None
    speaker_name: str | None
    text: str
    start_time: float
    end_time: float
    confidence: float | None
    segment_index: int


class ActionItemOut(BaseSchema):
    id: uuid.UUID
    task: str
    assigned_to: str | None
    deadline: str | None
    is_completed: bool
    priority: str | None
    created_at: datetime


class ActionItemUpdate(BaseSchema):
    is_completed: bool | None = None
    assigned_to: str | None = None
    deadline: str | None = None


class MeetingOut(BaseSchema):
    id: uuid.UUID
    title: str
    status: str
    source: str
    original_filename: str | None
    file_size_bytes: int | None
    duration_seconds: float | None
    language: str | None
    word_count: int | None
    summary: str | None
    mom: str | None
    key_decisions: list | None
    topics: list | None
    processing_error: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class MeetingDetailOut(MeetingOut):
    transcript: str | None
    participants: list[ParticipantOut] = []
    action_items: list[ActionItemOut] = []
    transcript_segments: list[TranscriptSegmentOut] = []


class MeetingListOut(BaseSchema):
    items: list[MeetingOut]
    total: int
    page: int
    page_size: int
    total_pages: int


# ═══════════════════════════════════════════════════════════════
# AI
# ═══════════════════════════════════════════════════════════════

class SummarizeRequest(BaseSchema):
    meeting_id: uuid.UUID
    regenerate: bool = False


class ChatRequest(BaseSchema):
    question: str = Field(..., min_length=1, max_length=2000)
    meeting_ids: list[uuid.UUID] | None = None   # None = search all user's meetings
    top_k: int = Field(default=5, ge=1, le=20)


class ChatResponse(BaseSchema):
    answer: str
    sources: list[dict[str, Any]] = []   # [{meeting_id, segment, score}]
    model_used: str


class GenerateMomRequest(BaseSchema):
    meeting_id: uuid.UUID
    regenerate: bool = False


# ═══════════════════════════════════════════════════════════════
# Reports
# ═══════════════════════════════════════════════════════════════

class ReportOut(BaseSchema):
    id: uuid.UUID
    meeting_id: uuid.UUID
    report_type: str
    format: str
    file_size_bytes: int | None
    download_count: int
    created_at: datetime


# ═══════════════════════════════════════════════════════════════
# Processing status (SSE / polling)
# ═══════════════════════════════════════════════════════════════

class ProcessingStatusOut(BaseSchema):
    meeting_id: uuid.UUID
    status: str
    progress_percent: int | None = None
    current_step: str | None = None
    error: str | None = None


# ═══════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════

class HealthOut(BaseSchema):
    status: str
    version: str
    db: bool
    redis: bool
    storage: str
