from __future__ import annotations

from fastapi import Depends, HTTPException, status
from app.core.models import RoleEnum, User
from app.routers.auth import get_current_user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in {
        RoleEnum.admin,
        RoleEnum.superadmin,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دسترسی مدیریتی لازم است.",
        )
    return current_user


def require_superadmin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != RoleEnum.superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دسترسی مدیر ارشد لازم است.",
        )
    return current_user
