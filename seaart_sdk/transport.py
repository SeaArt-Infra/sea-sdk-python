from __future__ import annotations

import json
import socket
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from email.message import Message
from urllib import error, request

from .errors import ERR_GENERAL, ERR_NETWORK, SeaArtError


@dataclass(slots=True)
class TransportClient:
    api_key: str
    base_url: str
    project: str
    user_agent: str
    timeout: float

    def request(
        self,
        method: str,
        path: str,
        body: object | None,
        headers: Mapping[str, Sequence[str]] | None,
    ) -> tuple[int, bytes]:
        req = self._build_request(method, path, body, headers)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return response.status, response.read()
        except error.HTTPError as exc:
            return exc.code, exc.read()
        except (error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise SeaArtError(kind=ERR_NETWORK, message=f"request failed: {exc}") from exc

    def request_raw(
        self,
        method: str,
        path: str,
        body: bytes | None,
        headers: Mapping[str, Sequence[str]] | None,
    ) -> tuple[int, dict[str, str], bytes]:
        req = self._build_raw_request(method, path, body, headers)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return response.status, _headers_to_dict(response.headers), response.read()
        except error.HTTPError as exc:
            return exc.code, _headers_to_dict(exc.headers), exc.read()
        except (error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise SeaArtError(kind=ERR_NETWORK, message=f"request failed: {exc}") from exc

    def request_stream(
        self,
        method: str,
        path: str,
        body: object | None,
        headers: Mapping[str, Sequence[str]] | None,
    ):
        req = self._build_request(method, path, body, headers)
        try:
            return request.urlopen(req, timeout=self.timeout)
        except error.HTTPError as exc:
            return exc
        except (error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise SeaArtError(kind=ERR_NETWORK, message=f"request failed: {exc}") from exc

    def _build_request(
        self,
        method: str,
        path: str,
        body: object | None,
        headers: Mapping[str, Sequence[str]] | None,
    ) -> request.Request:
        data = None
        if body is not None:
            try:
                data = json.dumps(body).encode("utf-8")
            except TypeError as exc:
                raise SeaArtError(
                    kind=ERR_GENERAL,
                    message=f"failed to marshal request: {exc}",
                ) from exc

        return self._new_request(method, path, data, headers)

    def _build_raw_request(
        self,
        method: str,
        path: str,
        body: bytes | None,
        headers: Mapping[str, Sequence[str]] | None,
    ) -> request.Request:
        return self._new_request(method, path, body, headers)

    def _new_request(
        self,
        method: str,
        path: str,
        data: bytes | None,
        headers: Mapping[str, Sequence[str]] | None,
    ) -> request.Request:
        request_headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": self.user_agent,
        }
        if self.project:
            request_headers["X-Project"] = self.project
        if headers:
            for key, values in headers.items():
                request_headers[key] = ", ".join(values)

        return request.Request(
            url=f"{self.base_url}{path}",
            data=data,
            headers=request_headers,
            method=method,
        )


def _headers_to_dict(headers: Message) -> dict[str, str]:
    return {key: value for key, value in headers.items()}
