from __future__ import annotations

import json
from dataclasses import dataclass, field

from .errors import ERR_GENERAL, SeaArtError
from .llm_types import RawResponse
from .request_options import RequestOption, build_request_options
from .transport import TransportClient


@dataclass(slots=True)
class PassthroughResponse:
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: RawResponse = b""


class PassthroughService:
    def __init__(self, client: TransportClient) -> None:
        self._client = client

    def request(
        self,
        method: str,
        path: str,
        body: object | None = None,
        *options: RequestOption,
    ) -> PassthroughResponse:
        payload = None
        if body is not None:
            try:
                payload = json.dumps(body).encode("utf-8")
            except TypeError as exc:
                raise SeaArtError(
                    kind=ERR_GENERAL,
                    message=f"failed to marshal request: {exc}",
                ) from exc
        return self.request_raw(method, path, payload, *options)

    def request_raw(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        *options: RequestOption,
    ) -> PassthroughResponse:
        request_options = build_request_options(options)
        status, headers, payload = self._client.request_raw(
            method,
            _normalize_passthrough_path(path),
            body,
            request_options.headers,
        )
        return PassthroughResponse(status_code=status, headers=headers, body=payload)

    def get(self, path: str, *options: RequestOption) -> PassthroughResponse:
        return self.request_raw("GET", path, None, *options)

    def post(self, path: str, body: object | None = None, *options: RequestOption) -> PassthroughResponse:
        return self.request("POST", path, body, *options)

    def put(self, path: str, body: object | None = None, *options: RequestOption) -> PassthroughResponse:
        return self.request("PUT", path, body, *options)

    def delete(self, path: str, body: object | None = None, *options: RequestOption) -> PassthroughResponse:
        return self.request("DELETE", path, body, *options)


def _normalize_passthrough_path(raw: str) -> str:
    path = raw.strip()
    if not path:
        raise SeaArtError(kind=ERR_GENERAL, message="passthrough path is required")
    if path.startswith(("http://", "https://")):
        raise SeaArtError(kind=ERR_GENERAL, message="passthrough path must be relative")
    if not path.startswith("/"):
        path = "/" + path
    return path
