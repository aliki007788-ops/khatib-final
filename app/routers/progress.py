from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import User
from app.routers.auth import get_current_user
from app.schemas.progress import DimensionTrendResponse, ProgressSummaryResponse
from app.services import progress_engine

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("/summary", response_model=ProgressSummaryResponse)
def get_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    summary = progress_engine.compute_summary(db, current_user.id)
    return ProgressSummaryResponse(**summary.__dict__)


@router.get("/trends", response_model=list[DimensionTrendResponse])
def get_trends(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trends = progress_engine.compute_dimension_trends(db, current_user.id)
    return [DimensionTrendResponse(**t.__dict__) for t in trends]
