"""Allow multiple ``create_app()`` instances during pytest (duplicate app names)."""

from sanic import Sanic

Sanic.test_mode = True
