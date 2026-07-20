from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.market_insight import MarketInsightsResponse
from app.services.market_insight_service import (
    get_last_updated,
    get_period_label,
    get_top_books,
    get_top_themes,
)

router = APIRouter(prefix="/market-insights", tags=["market-insights"])


@router.get("")
def get_market_insights(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    data = MarketInsightsResponse(
        period_label=get_period_label(db),
        last_updated=get_last_updated(db),
        books=get_top_books(db, limit=10),
        themes=get_top_themes(db, limit=10),
    )
    return {"success": True, "data": data.model_dump(mode="json")}
