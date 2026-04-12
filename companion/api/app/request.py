"""Sanic Request subclass with validated query/body payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from sanic import Request


class ValidatedRequest(Request):
    """Adds ``validated_data`` set by ``@validate_query`` / future body validators."""

    # Parent already has __slots__; only list new attributes here.
    __slots__ = ("validated_data",)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.validated_data: BaseModel | None = None
