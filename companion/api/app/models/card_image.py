"""Dithered bitmap metadata for ESP32 display."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel

from app.models.common import utc_now


class CardImage(SQLModel, table=True):
    __tablename__ = "card_images"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    card_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("cards.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    local_path: str
    cached_at: datetime = Field(default_factory=utc_now)
