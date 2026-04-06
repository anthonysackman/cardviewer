"""Set lookup — seeded from Scryfall /sets."""

from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class CardSet(SQLModel, table=True):
    __tablename__ = "sets"

    code: str = Field(primary_key=True)
    name: str
    released_at: Optional[date] = None
    set_type: Optional[str] = None
    icon_svg_uri: Optional[str] = None
