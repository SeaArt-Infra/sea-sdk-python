from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from types import NoneType, UnionType
from typing import Any, TypeVar, get_args, get_origin, get_type_hints

from .errors import ERR_GENERAL, SeaArtError

T = TypeVar("T")


def decode(raw: bytes | str | Any, target_type: type[T]) -> T:
    payload = raw
    if isinstance(raw, bytes):
        payload = json.loads(raw.decode("utf-8"))
    elif isinstance(raw, str):
        payload = json.loads(raw)

    try:
        return _convert(payload, target_type)
    except SeaArtError:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        raise SeaArtError(
            kind=ERR_GENERAL,
            message=f"failed to decode response: {exc}",
        ) from exc


def _convert(value: Any, annotation: Any) -> Any:
    if annotation in (Any, object) or annotation is None:
        return value
    if value is None:
        return None

    origin = get_origin(annotation)
    if origin in (list, list[str], Sequence):
        item_type = get_args(annotation)[0] if get_args(annotation) else Any
        return [_convert(item, item_type) for item in value]
    if origin in (dict, Mapping):
        args = get_args(annotation)
        value_type = args[1] if len(args) == 2 else Any
        return {key: _convert(item, value_type) for key, item in value.items()}
    if origin in (tuple,):
        args = get_args(annotation)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_convert(item, args[0]) for item in value)
    if origin in (UnionType, getattr(__import__("typing"), "Union")):
        for candidate in get_args(annotation):
            if candidate is NoneType:
                if value is None:
                    return None
                continue
            try:
                return _convert(value, candidate)
            except Exception:
                continue
        return value
    if isinstance(annotation, type) and is_dataclass(annotation):
        return _convert_dataclass(value, annotation)
    return value


def _convert_dataclass(value: Any, dataclass_type: type[Any]) -> Any:
    if not isinstance(value, Mapping):
        return value

    type_hints = get_type_hints(dataclass_type)
    kwargs: dict[str, Any] = {}
    for field_info in fields(dataclass_type):
        if field_info.name.startswith("_"):
            continue
        json_key = field_info.metadata.get("json", field_info.name)
        if json_key not in value:
            continue
        kwargs[field_info.name] = _convert(
            value[json_key],
            type_hints.get(field_info.name, field_info.type),
        )
    return dataclass_type(**kwargs)
