from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class MapperInterface(ABC):
    @abstractmethod
    def map(self, source_obj: Any, target_cls: type[T]) -> T:
        pass

    @abstractmethod
    def map_list(self, source_list: list[Any], target_cls: type[T]) -> list[T]:
        pass

    @abstractmethod
    def register(
        self, source_cls: type[Any], target_cls: type[T], func: Callable[[Any], T]
    ) -> None:
        pass
