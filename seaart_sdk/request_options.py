from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

HeaderValue = str | Sequence[str]


@dataclass(slots=True)
class RequestOptions:
    headers: dict[str, list[str]] = field(default_factory=dict)


RequestOption = Callable[[RequestOptions], None]


def build_request_options(options: Sequence[RequestOption]) -> RequestOptions:
    config = RequestOptions()
    for option in options:
        if option is not None:
            option(config)
    return config


def with_header(key: str, value: str) -> RequestOption:
    def apply(options: RequestOptions) -> None:
        options.headers[key] = [value]

    return apply


def with_headers(headers: Mapping[str, HeaderValue]) -> RequestOption:
    def apply(options: RequestOptions) -> None:
        for key, value in headers.items():
            if isinstance(value, str):
                values = [value]
            else:
                values = [item for item in value]
            options.headers[key] = values

    return apply
