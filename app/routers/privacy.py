from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import User
from app.routers.auth import get_current_user
from app.schemas.privacy import DeleteAccountRequest, ExportDataResponse
from app.services.privacy_service import build_user_export, delete_user_account

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


@router.get("/export", response_model=ExportDataResponse)
def export_my_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.deleted_at:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="این حساب قبلاً حذف شده است.")
    data = build_user_export(db, current_user)
    return data


@router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    payload: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.confirmation != "DELETE_ACCOUNT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای حذف حساب باید عبارت DELETE_ACCOUNT را ارسال کنید.",
        )
    if current_user.role.value == "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب superadmin از طریق این مسیر حذف نمی‌شود.",
        )
    delete_user_account(db, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
