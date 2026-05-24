"""
api/routes/auth.py
Authentication endpoints: register, login, refresh, logout, me.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.deps import get_current_user
from db.database import get_db
from models.orm import RefreshToken, User, UserRole, Workspace, WorkspacePlan
from models.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from services.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from utils.slugify import make_unique_slug

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ── Register ──────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check slug uniqueness
    slug_exists = await db.execute(
        select(Workspace).where(Workspace.slug == body.workspace.slug)
    )
    if slug_exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Workspace slug already taken")

    # Create workspace
    workspace = Workspace(
        name=body.workspace.name,
        slug=body.workspace.slug,
        plan=WorkspacePlan.FREE,
    )
    db.add(workspace)
    await db.flush()   # get workspace.id before user insert

    # Create user as admin of their own workspace
    user = User(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=UserRole.ADMIN,
        workspace_id=workspace.id,
        is_verified=False,
    )
    db.add(user)
    await db.flush()

    # Issue tokens
    access_token = create_access_token(user.id, workspace.id, user.role.value)
    refresh_str, refresh_exp = create_refresh_token(user.id)

    db.add(RefreshToken(token=refresh_str, user_id=user.id, expires_at=refresh_exp))
    await db.commit()

    log.info("user_registered", user_id=str(user.id), workspace=workspace.slug)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_str,
        expires_in=60 * 60,  # 1 hour
    )


# ── Login ─────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    access_token = create_access_token(user.id, user.workspace_id, user.role.value)
    refresh_str, refresh_exp = create_refresh_token(user.id)

    db.add(RefreshToken(token=refresh_str, user_id=user.id, expires_at=refresh_exp))
    await db.commit()

    log.info("user_login", user_id=str(user.id))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_str,
        expires_in=60 * 60,
    )


# ── Refresh ───────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_refresh_token(body.refresh_token)
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Look up stored token
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == body.refresh_token,
            RefreshToken.revoked == False,
        )
    )
    stored = result.scalar_one_or_none()
    if not stored or stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")

    # Rotate: revoke old, issue new
    stored.revoked = True

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(user.id, user.workspace_id, user.role.value)
    new_refresh, new_exp = create_refresh_token(user.id)
    db.add(RefreshToken(token=new_refresh, user_id=user.id, expires_at=new_exp))
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=new_refresh, expires_in=60 * 60)


# ── Logout ────────────────────────────────────────────────────

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == body.refresh_token)
    )
    token_row = result.scalar_one_or_none()
    if token_row:
        token_row.revoked = True
        await db.commit()


# ── Me ────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
