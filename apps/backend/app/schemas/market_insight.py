from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BestsellerBookResponse(BaseModel):
    id: UUID
    rank: int
    title: str
    author: str | None
    publisher: str | None
    category: str | None
    sales_volume: int | None

    model_config = ConfigDict(from_attributes=True)


class BestsellerThemeResponse(BaseModel):
    category: str
    total_volume: int
    book_count: int


class MarketInsightsResponse(BaseModel):
    source: str = "publishnews"
    period_label: str | None
    last_updated: datetime | None
    books: list[BestsellerBookResponse]
    themes: list[BestsellerThemeResponse]
