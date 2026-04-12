"""Shared constants and small enums for API contracts."""

from enum import StrEnum


class ResponseFormat(StrEnum):
    """How to shape a card response (e.g. random card)."""

    COMPACT = "compact"
