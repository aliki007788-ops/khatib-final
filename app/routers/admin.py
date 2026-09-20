from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.admin_dependencies import require_admin
from app.core.db import get_db
from app.core.models import (
    AuditLog,
    PlanEnum,
    Subscription,
    SubscriptionStatus,
    Transaction,
    User,
)
from app.schemas.admin import (
    AdminStatsResponse,
    AdminUserResponse,
    SetUserActiveRequest,
    SetUserPlanRequest,
)
from app.services.admin_service import get_admin_stats

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsResponse)
def stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return get_admin_stats(db)


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(
    search: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(User).order_by(User.created_at.desc())
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where((User.email.ilike(pattern)) | (User.name.ilike(pattern)))
    users = db.execute(query.offset(offset).limit(limit)).scalars().all()
    return users


@router.get("/users/{user_id}", response_model=AdminUserResponse)
def get_user(user_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "کاربر یافت نشد.")
    return user


@router.patch("/users/{user_id}/plan", response_model=AdminUserResponse)
def set_user_plan(
    user_id: str,
    payload: SetUserPlanRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "کاربر یافت نشد.")
    try:
        user.plan = PlanEnum(payload.plan)
    except ValueError:
        raise HTTPException(400, "پلن نامعتبر است.")
    db.add(AuditLog(user_id=admin.id, action="admin_set_user_plan",
                    detail=f"target_user={user.id};plan={user.plan.value}"))
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/active", response_model=AdminUserResponse)
def set_user_active(
    user_id: str,
    payload: SetUserActiveRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "کاربر یافت نشد.")
    if user.id == admin.id and not payload.active:
        raise HTTPException(400, "مدیر نمی‌تواند خودش را غیرفعال کند.")
    user.active = payload.active
    db.add(AuditLog(user_id=admin.id, action="admin_change_user_active",
                    detail=f"target_user={user.id};active={payload.active}"))
    db.commit()
    db.refresh(user)
    return user


@router.get("/audit")
def audit_logs(
    user_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    logs = db.execute(query.limit(limit)).scalars().all()
    return [
        {
            "id": item.id,
            "user_id": item.user_id,
            "action": item.action,
            "detail": item.detail,
            "ip_address": item.ip_address,
            "created_at": item.created_at.isoformat(),
        }
        for item in logs
    ]


@router.get("/transactions")
def list_transactions(
    status_filter: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(Transaction).order_by(Transaction.created_at.desc())
    if status_filter:
        query = query.where(Transaction.status == status_filter)
    rows = db.execute(query.limit(limit)).scalars().all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "plan": row.plan.value,
            "amount_toman": row.amount_toman,
            "status": row.status.value,
            "provider": row.provider.value,
            "authority": row.authority,
            "ref_id": row.ref_id,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/subscriptions")
def list_subscriptions(
    active_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(Subscription).order_by(Subscription.created_at.desc())
    if active_only:
        query = query.where(Subscription.status == SubscriptionStatus.active)
    rows = db.execute(query.limit(limit)).scalars().all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "plan": row.plan.value,
            "status": row.status.value,
            "starts_at": row.starts_at.isoformat(),
            "expires_at": row.expires_at.isoformat(),
        }
        for row in rows
    ]
