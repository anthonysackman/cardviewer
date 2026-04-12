from enum import StrEnum
from app.clients.base import BaseClient
class BaseValue(StrEnum):
    BASE_URL = "https://api.scryfall.com"

class ScryfallClient(BaseClient):
    def __init__(self) -> None:
        super().__init__(BaseValue.BASE_URL)

    async def get_random_card(self) -> dict:
        return await self.get("/cards/random")