from __future__ import annotations

import json
from http import HTTPStatus
from typing import Iterator

from .errors import ERR_GENERAL, ERR_NETWORK, SeaArtError, new_http_error
from .llm_types import JSONMap, RawResponse, StreamEvent
from .request_options import RequestOption, build_request_options, move_model_to_header
from .transport import TransportClient

PATH_CHAT_COMPLETIONS = "/chat/completions"
PATH_MESSAGES = "/v1/messages"
PATH_RESPONSES = "/responses"
PATH_RERANK = "/rerank"
PATH_EMBEDDINGS = "/v1/embeddings"
PATH_MODELS = "/v1/models"


class LLMService:
    def __init__(self, client: TransportClient) -> None:
        self._client = client

    def chat_completions(self, payload: JSONMap, *options: RequestOption) -> RawResponse:
        if _is_streaming(payload):
            raise _unsupported_streaming_error("chat_completions", "chat_completions_stream")
        return self._do_raw_json("POST", PATH_CHAT_COMPLETIONS, payload, *options)

    def chat_completions_stream(
        self,
        payload: JSONMap,
        *options: RequestOption,
    ) -> Iterator[StreamEvent]:
        return self._do_sse("POST", PATH_CHAT_COMPLETIONS, _ensure_streaming_payload(payload), *options)

    def messages(self, payload: JSONMap, *options: RequestOption) -> RawResponse:
        if _is_streaming(payload):
            raise _unsupported_streaming_error("messages", "messages_stream")
        return self._do_raw_json("POST", PATH_MESSAGES, payload, *options)

    def messages_stream(self, payload: JSONMap, *options: RequestOption) -> Iterator[StreamEvent]:
        return self._do_sse("POST", PATH_MESSAGES, _ensure_streaming_payload(payload), *options)

    def responses(self, payload: JSONMap, *options: RequestOption) -> RawResponse:
        if _is_streaming(payload):
            raise _unsupported_streaming_error("responses", "responses_stream")
        return self._do_raw_json("POST", PATH_RESPONSES, payload, *options)

    def responses_stream(self, payload: JSONMap, *options: RequestOption) -> Iterator[StreamEvent]:
        return self._do_sse("POST", PATH_RESPONSES, _ensure_streaming_payload(payload), *options)

    def rerank(self, payload: JSONMap, *options: RequestOption) -> RawResponse:
        return self._do_raw_json("POST", PATH_RERANK, payload, *options)

    def embeddings(self, payload: JSONMap, *options: RequestOption) -> RawResponse:
        return self._do_raw_json("POST", PATH_EMBEDDINGS, payload, *options)

    def list_models(self, *options: RequestOption) -> RawResponse:
        return self._do_raw_json("GET", PATH_MODELS, None, *options)

    def _do_raw_json(
        self,
        method: str,
        path: str,
        body: JSONMap | None,
        *options: RequestOption,
    ) -> RawResponse:
        request_options = build_request_options(options)
        if body is None:
            request_body, headers = body, request_options.headers
        else:
            request_body, headers = move_model_to_header(body, request_options.headers)
        status, payload = self._client.request(method, path, request_body, headers)
        if status >= 400:
            raise _http_error(status, payload)
        return payload

    def _do_sse(
        self,
        method: str,
        path: str,
        body: JSONMap,
        *options: RequestOption,
    ) -> Iterator[StreamEvent]:
        request_options = build_request_options(options)
        request_body, headers = move_model_to_header(body, request_options.headers)
        response = self._client.request_stream(method, path, request_body, headers)
        if response.status >= 400:
            payload = response.read()
            response.close()
            raise _http_error(response.status, payload)
        return _iterate_sse(response)


def _iterate_sse(response) -> Iterator[StreamEvent]:
    event_name = ""
    data_lines: list[str] = []

    def emit() -> StreamEvent | None:
        nonlocal event_name, data_lines
        if not data_lines and not event_name:
            return None

        data = "\n".join(data_lines)
        event = StreamEvent(event=event_name)
        event_name = ""
        data_lines = []

        if data == "[DONE]":
            event.done = True
            return event
        if data:
            event.data = data.encode("utf-8")
        if event.event or event.data or event.done:
            return event
        return None

    try:
        while True:
            raw_line = response.readline()
            if raw_line == b"":
                last = emit()
                if last is not None:
                    yield last
                return

            line = raw_line.decode("utf-8").rstrip("\r\n")
            if line == "":
                event = emit()
                if event is not None:
                    yield event
                    if event.done:
                        return
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
    except SeaArtError:
        raise
    except Exception as exc:
        yield StreamEvent(
            err=SeaArtError(kind=ERR_NETWORK, message=f"stream read failed: {exc}")
        )
    finally:
        response.close()


def _is_streaming(payload: JSONMap) -> bool:
    return bool(payload.get("stream") is True)


def _ensure_streaming_payload(payload: JSONMap) -> JSONMap:
    cloned = dict(payload)
    cloned["stream"] = True
    return cloned


def _unsupported_streaming_error(method_name: str, stream_method: str) -> SeaArtError:
    return SeaArtError(
        kind=ERR_GENERAL,
        message=f"stream=true is not supported by {method_name}; use {stream_method} instead",
    )


def _http_error(status: int, payload: bytes) -> SeaArtError:
    message = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "HTTP error"
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except Exception:
        return new_http_error(status, message)

    if isinstance(parsed, dict):
        nested_error = parsed.get("error")
        if isinstance(nested_error, dict):
            if nested_error.get("error_message"):
                message = str(nested_error["error_message"])
            elif nested_error.get("message"):
                message = str(nested_error["message"])
        elif parsed.get("message"):
            message = str(parsed["message"])
    return new_http_error(status, message)
