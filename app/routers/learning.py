from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import User
from app.routers.auth import get_current_user
from app.schemas.learning import (
    DailyRecommendationResponse,
    LevelResponse,
    ScenarioResponse,
    StartScenarioResponse,
)
from app.services import learning_engine

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/levels", response_model=list[LevelResponse])
def list_levels(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = learning_engine.get_levels_with_progress(db, current_user.id)
    return [
        LevelResponse(
            id=i.level.id, code=i.level.code, name_fa=i.level.name_fa,
            order_index=i.level.order_index, description_fa=i.level.description_fa,
            unlocked=i.unlocked, completed_count=i.completed_count, total_count=i.total_count,
        )
        for i in items
    ]


@router.get("/levels/{level_id}/scenarios", response_model=list[ScenarioResponse])
def list_scenarios(level_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        items = learning_engine.get_scenarios_for_level(db, current_user.id, level_id)
    except learning_engine.LearningEngineError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message)

    return [
        ScenarioResponse(
            id=i.scenario.id, category=i.scenario.category, order_index=i.scenario.order_index,
            title_fa=i.scenario.title_fa, description_fa=i.scenario.description_fa,
            key_vocabulary=i.scenario.key_vocabulary, status=i.status, unlocked=i.unlocked,
        )
        for i in items
    ]


@router.post("/scenarios/{scenario_id}/start", response_model=StartScenarioResponse)
def start_scenario(scenario_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        conv = learning_engine.start_scenario(db, current_user, scenario_id)
    except learning_engine.LearningEngineError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message)
    return StartScenarioResponse(conversation_id=conv.id)


@router.post("/scenarios/{scenario_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
def complete_scenario(scenario_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        learning_engine.complete_scenario(db, current_user, scenario_id)
    except learning_engine.LearningEngineError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message)
    return None


@router.get("/daily-recommendation", response_model=DailyRecommendationResponse)
def daily_recommendation(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rec = learning_engine.get_daily_recommendation(db, current_user)
    return DailyRecommendationResponse(**rec.__dict__)
