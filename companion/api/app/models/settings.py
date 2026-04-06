"""Single-row app settings (id is always 1)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import Field, SQLModel

from app.models.common import utc_now


class AppSettings(SQLModel, table=True):
    __tablename__ = "settings"

    id: int = Field(default=1, primary_key=True)
    mode: str
    current_card_id: Optional[UUID] = Field(default=None, foreign_key="cards.id")
    updated_at: datetime = Field(default_factory=utc_now)
