from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    name: str = ""

    @abstractmethod
    async def run(self, input: dict) -> dict:
        ...

    def requires_input_from(self) -> list[str]:
        return []

    def provides_output_to(self) -> list[str]:
        return []
