"""Validated query-string models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.constants import ResponseFormat


class RandomCardQuery(BaseModel):
    """Query params for ``GET /scryfall/cards/random``."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    format: ResponseFormat | None = Field(
        default=None,
        description="Omit or use compact for ESP-sized payload",
    )
