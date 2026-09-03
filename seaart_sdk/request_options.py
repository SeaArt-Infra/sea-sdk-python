from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from .errors import ERR_GENERAL, SeaArtError

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


def move_model_to_header(
    body: Mapping[str, object], headers: Mapping[str, Sequence[str]]
) -> tuple[dict[str, object], dict[str, list[str]]]:
    """Move a request model from the JSON body to the gateway routing header."""
    request_body = dict(body)
    request_headers = {key: list(values) for key, values in headers.items()}

    if "model" not in request_body:
        return request_body, request_headers

    model = request_body.pop("model")
    if not isinstance(model, str) or not model.strip():
        raise SeaArtError(kind=ERR_GENERAL, message="model must be a non-empty string")
    if any(key.lower() == "x-model" for key in request_headers):
        raise SeaArtError(kind=ERR_GENERAL, message="model and X-Model cannot both be set")

    request_headers["X-Model"] = [model]
    return request_body, request_headers


def keep_model_in_body(
    body: Mapping[str, object], headers: Mapping[str, Sequence[str]]
) -> tuple[dict[str, object], dict[str, list[str]]]:
    """Validate an LLM model while keeping it in the serialized JSON body."""
    request_body = dict(body)
    request_headers = {key: list(values) for key, values in headers.items()}

    if any(key.lower() == "x-model" for key in request_headers):
        raise SeaArtError(
            kind=ERR_GENERAL,
            message="X-Model is not supported for LLM requests; set model in the request body",
        )

    if "model" in request_body:
        model = request_body["model"]
        if not isinstance(model, str) or not model.strip():
            raise SeaArtError(kind=ERR_GENERAL, message="model must be a non-empty string")
    return request_body, request_headers
