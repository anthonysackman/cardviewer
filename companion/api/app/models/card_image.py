"""Dithered bitmap metadata for ESP32 display."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models.common import utc_now


class CardImage(SQLModel, table=True):
    __tablename__ = "card_images"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    card_id: UUID = Field(foreign_key="cards.id")
    local_path: str
    cached_at: datetime = Field(default_factory=utc_now)
