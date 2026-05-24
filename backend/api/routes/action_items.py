"""
api/routes/action_items.py
CRUD for action items across meetings.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from db.database import get_db
from models.orm import ActionItem, Meeting, User
from models.schemas import ActionItemOut, ActionItemUpdate

router = APIRouter(prefix="/action-items", tags=["action-items"])


@router.get("", response_model=list[ActionItemOut])
async def list_action_items(
    completed: bool | None = Query(default=None),
    assigned_to: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all action items across the workspace, with optional filters."""
    q = (
        select(ActionItem)
        .join(Meeting, Meeting.id == ActionItem.meeting_id)
        .where(Meeting.workspace_id == current_user.workspace_id)
    )
    if completed is not None:
        q = q.where(ActionItem.is_completed == completed)
    if assigned_to:
        q = q.where(ActionItem.assigned_to.ilike(f"%{assigned_to}%"))

    q = q.order_by(ActionItem.created_at.desc()).limit(limit)
    rows = await db.execute(q)
    return [ActionItemOut.model_validate(a) for a in rows.scalars().all()]


@router.patch("/{item_id}", response_model=ActionItemOut)
async def update_action_item(
    item_id: uuid.UUID,
    body: ActionItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ActionItem)
        .join(Meeting, Meeting.id == ActionItem.meeting_id)
        .where(
            ActionItem.id == item_id,
            Meeting.workspace_id == current_user.workspace_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    if body.is_completed is not None:
        item.is_completed = body.is_completed
    if body.assigned_to is not None:
        item.assigned_to = body.assigned_to
    if body.deadline is not None:
        item.deadline = body.deadline

    await db.commit()
    return ActionItemOut.model_validate(item)


@router.delete("/{item_id}", status_code=204)
async def delete_action_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ActionItem)
        .join(Meeting, Meeting.id == ActionItem.meeting_id)
        .where(
            ActionItem.id == item_id,
            Meeting.workspace_id == current_user.workspace_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")
    await db.delete(item)
    await db.commit()
