from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from email.message import Message
from unittest.mock import patch
from urllib.parse import urlparse

from seaart_sdk import Client, ClientConfig


class FakeResponse:
    def __init__(
        self,
        status: int,
        body: bytes = b"",
        lines: list[bytes] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self._lines = list(lines or [])
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def read(self) -> bytes:
        if self._lines:
            data = b"".join(self._lines)
            self._lines.clear()
            return data
        return self._body

    def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)

    def close(self) -> None:
        return


def make_client() -> Client:
    return Client(
        ClientConfig(
            api_key="test-key",
            model_base_url="https://modal.example.com",
            llm_base_url="https://llm.example.com",
            passthrough_base_url="https://modal.example.com",
            timeout=5.0,
        )
    )


def json_response(status: int, payload: object, headers: dict[str, str] | None = None) -> FakeResponse:
    return FakeResponse(status=status, body=json.dumps(payload).encode("utf-8"), headers=headers)


def sse_response(*chunks: str) -> FakeResponse:
    lines: list[bytes] = []
    for chunk in chunks:
        lines.extend(line.encode("utf-8") for line in chunk.splitlines(keepends=True))
    return FakeResponse(status=200, lines=lines)


def request_json(req) -> dict:
    if not getattr(req, "data", None):
        return {}
    return json.loads(req.data.decode("utf-8"))


def request_headers(req) -> dict[str, str]:
    return dict(req.header_items())


def request_body(req) -> bytes:
    return getattr(req, "data", None) or b""


def request_path(req) -> str:
    return urlparse(req.full_url).path


@contextmanager
def patch_urlopen(handler: Callable[[object], FakeResponse]) -> Iterator[None]:
    def wrapped(req, *args, **kwargs):
        return handler(req)

    with patch("seaart_sdk.transport.request.urlopen", side_effect=wrapped):
        yield
