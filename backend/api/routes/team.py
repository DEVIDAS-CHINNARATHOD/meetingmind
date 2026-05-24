"""
api/routes/team.py
Workspace team management: list members, invite, change role, remove.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.deps import get_current_user, require_admin, require_manager_or_above
from db.database import get_db
from models.orm import User, UserRole, Workspace
from models.schemas import UserOut
from services.auth import create_access_token, hash_password

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/team", tags=["team"])


# ── Schemas ───────────────────────────────────────────────────

class InviteRequest(BaseModel):
    email: EmailStr
    name: str
    role: UserRole = UserRole.VIEWER


class RoleUpdateRequest(BaseModel):
    role: UserRole


class InviteOut(BaseModel):
    message: str
    invited_email: str
    temp_access_token: str   # In prod: send via email; here we return it for testing


# ── List members ──────────────────────────────────────────────

@router.get("/members", response_model=list[UserOut])
async def list_members(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await db.execute(
        select(User)
        .where(User.workspace_id == current_user.workspace_id)
        .order_by(User.created_at)
    )
    return [UserOut.model_validate(u) for u in rows.scalars().all()]


# ── Invite member ─────────────────────────────────────────────

@router.post("/invite", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
async def invite_member(
    body: InviteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    """
    Invite a new member to the workspace.
    Creates the user with a temporary password and returns a short-lived
    access token (in production this would be emailed as a magic link).
    """
    # Check not already a member
    existing = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists",
        )

    # Admins cannot invite another Admin (only owner can do that)
    if body.role == UserRole.ADMIN and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403, detail="Only admins can invite other admins"
        )

    import secrets
    tmp_password = secrets.token_urlsafe(16)

    new_user = User(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(tmp_password),
        role=body.role,
        workspace_id=current_user.workspace_id,
        is_active=True,
        is_verified=False,
    )
    db.add(new_user)
    await db.flush()

    # Short-lived token (24h) for the invite link
    invite_token = create_access_token(
        new_user.id, current_user.workspace_id, new_user.role.value
    )

    await db.commit()

    log.info(
        "member_invited",
        invited=body.email,
        role=body.role.value,
        invited_by=str(current_user.id),
    )

    # background_tasks.add_task(send_invite_email, body.email, invite_token)

    return InviteOut(
        message=f"{body.name} has been invited as {body.role.value}",
        invited_email=body.email,
        temp_access_token=invite_token,
    )


# ── Update role ───────────────────────────────────────────────

@router.patch("/members/{user_id}/role", response_model=UserOut)
async def update_member_role(
    user_id: uuid.UUID,
    body: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Only admins can change roles."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.workspace_id == current_user.workspace_id,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = user.role
    user.role = body.role
    await db.commit()

    log.info(
        "role_updated",
        user_id=str(user_id),
        old=old_role.value,
        new=body.role.value,
        by=str(current_user.id),
    )
    return UserOut.model_validate(user)


# ── Remove member ─────────────────────────────────────────────

@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Remove a member from the workspace (soft-deactivate)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.workspace_id == current_user.workspace_id,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    await db.commit()
    log.info("member_removed", user_id=str(user_id), by=str(current_user.id))


# ── Workspace info ────────────────────────────────────────────

@router.get("/workspace")
async def get_workspace(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Workspace).where(Workspace.id == current_user.workspace_id)
    )
    ws = result.scalar_one()

    member_count_q = await db.execute(
        select(User).where(
            User.workspace_id == ws.id,
            User.is_active == True,
        )
    )
    members = member_count_q.scalars().all()

    return {
        "id": str(ws.id),
        "name": ws.name,
        "slug": ws.slug,
        "plan": ws.plan.value,
        "monthly_meeting_limit": ws.monthly_meeting_limit,
        "storage_limit_gb": ws.storage_limit_gb,
        "member_count": len(members),
        "created_at": ws.created_at.isoformat(),
    }
