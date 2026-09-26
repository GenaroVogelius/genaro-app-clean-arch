from abc import abstractmethod
from typing import Any, Protocol


class PresenterInterface(Protocol):
    @abstractmethod
    async def present(self, *args: Any, **kwargs: Any) -> Any:
        pass
