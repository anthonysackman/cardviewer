"""Scryfall printing row — one row per card face printing."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel

from app.models.common import utc_now


class Card(SQLModel, table=True):
    __tablename__ = "cards"

    id: UUID = Field(primary_key=True)
    oracle_id: UUID
    name: str
    mana_cost: Optional[str] = None
    cmc: float
    type_line: str
    oracle_text: Optional[str] = None
    flavor_text: Optional[str] = None
    power: Optional[str] = None
    toughness: Optional[str] = None
    loyalty: Optional[str] = None
    rarity: str
    set_code: str
    set_name: str
    collector_number: str
    artist: str
    color_identity: list[str] = Field(
        sa_column=Column(ARRAY(String), nullable=False),
    )
    keywords: list[str] = Field(
        sa_column=Column(ARRAY(String), nullable=False),
    )
    watermark: Optional[str] = None
    price_usd: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(12, 4)),
    )
    price_usd_foil: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(12, 4)),
    )
    prints_search_uri: str
    art_crop_url: str
    cached_at: datetime = Field(default_factory=utc_now)
