from typing import Any, TypeVar

from app.domain.interfaces.mapper.mapper import MapperInterface

T = TypeVar("T")

_MAPS_ATTR = "_maps_registration"


def maps(source_cls: type, target_cls: type):
    def decorator(func):
        setattr(func, _MAPS_ATTR, (source_cls, target_cls))
        return func

    return decorator


class GlobalMapper(MapperInterface):
    _class_mappings: dict = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._class_mappings = {}
        for name, func in vars(cls).items():
            registration = getattr(func, _MAPS_ATTR, None)
            if registration is not None:
                cls._class_mappings[registration] = name

    def __init__(self):
        self._mappings = {
            key: getattr(self, method_name)
            for key, method_name in self._class_mappings.items()
        }

    def register(self, source_cls, target_cls, func):
        self._mappings[(source_cls, target_cls)] = func

    def _source_key(self, source_obj: Any):
        if isinstance(source_obj, list) and source_obj:
            return list[type(source_obj[0])]  # type: ignore[misc]
        return type(source_obj)

    def map(self, source_obj, target_cls: type[T], **kwargs) -> T:
        """
        Transforms a source object into a target object.
        The cardinality is determined by the registered function.
        When the source is a non-empty list, the key is resolved as list[ElementType].

        Args:
            source_obj: The source object to map
            target_cls: The target class type
            **kwargs: Extra arguments forwarded to the registered mapping function

        Returns:
            T: The result of the registered mapping function
        """
        key = (self._source_key(source_obj), target_cls)
        if key not in self._mappings:
            raise ValueError(f"There is no mapper registered for {key}")

        return self._mappings[key](source_obj, **kwargs)

    def map_list(self, source_list: list, target_cls: type[T]) -> list[T]:
        """
        Transforms a list of source objects into a list of target objects,
        applying the registered one-to-one mapping to each element.

        Args:
            source_list: The list of source objects to map
            target_cls: The target class type

        Returns:
            List[T]: A list of instances of the target class
        """
        if not source_list:
            return []

        key = (type(source_list[0]), target_cls)
        if key not in self._mappings:
            raise ValueError(f"There is no mapper registered for {key}")

        mapping_func = self._mappings[key]
        return [mapping_func(item) for item in source_list]
