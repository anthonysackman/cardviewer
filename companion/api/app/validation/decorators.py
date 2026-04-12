"""Central request validation decorators."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sanic.request import Request
from sanic.response import HTTPResponse, json

from app.request import ValidatedRequest

T = TypeVar("T", bound=BaseModel)


def _flat_query_args(request: Request) -> dict[str, str]:
    """First value per query key (Sanic ``RequestParameters``)."""
    return {k: request.args.get(k) for k in request.args}


def validate_query(model: type[T]) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Parse ``request.args`` with ``model``, set ``request.validated_data``, or return 422."""

    def decorator(handler: Callable[..., object]) -> Callable[..., object]:
        @wraps(handler)
        async def wrapper(request: Request, *args: object, **kwargs: object) -> HTTPResponse:
            if not isinstance(request, ValidatedRequest):
                raise RuntimeError(
                    "validate_query requires app configured with request_class=ValidatedRequest",
                )
            try:
                request.validated_data = model.model_validate(_flat_query_args(request))
            except ValidationError as e:
                return json(
                    {"error": "validation_error", "detail": e.errors()},
                    status=422,
                )
            return await handler(request, *args, **kwargs)  # type: ignore[misc]

        return wrapper

    return decorator
