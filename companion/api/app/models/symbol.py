"""Mana symbology — seeded from `/symbology`."""

from typing import Optional

from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel


class Symbol(SQLModel, table=True):
    __tablename__ = "symbols"

    symbol: str = Field(primary_key=True)
    label: str
    svg_uri: Optional[str] = None
    cmc: Optional[float] = None
    colors: Optional[list[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
    )
