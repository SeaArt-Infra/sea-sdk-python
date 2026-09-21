from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any
from http import HTTPStatus
from urllib.parse import quote, urlencode

from .errors import ERR_GENERAL, ERR_NETWORK, ERR_TASK_FAILED, ERR_TIMEOUT, SeaArtError, new_http_error
from .modal_types import (
    APIError,
    AudioScanRequest,
    AudioScanResponse,
    CharacterQualityScanRequest,
    CharacterQualityScanResponse,
    ComfyUIInput,
    ComfyUITemplateSpecsResponse,
    FaceScanRequest,
    FaceScanResponse,
    GenerationResponse,
    ImageScanRequest,
    ImageScanResponse,
    ModelSearchParams,
    ModelSearchResponse,
    PrechargeResponse,
    PollOption,
    Task,
    TaskStreamEvent,
    TaskStreamFrame,
    TextContentScanRequest,
    TextContentScanResponse,
    VisualStructuredTextFusionScanRequest,
    VisualStructuredTextFusionScanResponse,
    TextScanRequest,
    TextScanResponse,
    apply_poll_options,
)
from .request_options import RequestOption, build_request_options, move_model_to_header
from .serialization import decode
from .transport import TransportClient

STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
POLL_NETWORK_RETRY_LIMIT = 3
SSE_CONTENT_TYPE = "text/event-stream"


class ModalService:
    def __init__(self, client: TransportClient) -> None:
        self._client = client

    def create(self, body: dict[str, object], *options: RequestOption) -> Task:
        request_options = build_request_options(options)
        request_body, headers = move_model_to_header(body, request_options.headers)
        status, payload = self._client.request(
            "POST",
            "/v1/generation",
            request_body,
            headers,
        )
        if status >= 400:
            raise _http_error(status, payload)

        response = decode(payload, GenerationResponse)
        if not response.id:
            raise SeaArtError(kind="general", message="API returned no task ID")
        return Task(
            id=response.id,
            status=response.status,
            model=response.model,
            error=response.error,
            _service=self,
        )

    def precharge(self, body: dict[str, object], *options: RequestOption) -> PrechargeResponse:
        request_options = build_request_options(options)
        request_body, headers = move_model_to_header(body, request_options.headers)
        status, payload = self._client.request(
            "POST",
            "/v1/generation/precharge",
            request_body,
            headers,
        )
        if status >= 400:
            raise _http_error(status, payload)
        return decode(payload, PrechargeResponse)

    def create_comfyui_task(
        self,
        template_id: str,
        inputs: list[ComfyUIInput | dict[str, object]],
        high_memory: bool | None = None,
        *options: RequestOption,
    ) -> Task:
        """Create a ComfyUI quick-app task with the gateway-required request shape."""
        template_id = template_id.strip()
        if not template_id:
            raise SeaArtError(kind="general", message="template_id is required")
        if not inputs:
            raise SeaArtError(kind="general", message="inputs is required")

        raw_inputs: list[dict[str, object]] = []
        for item in inputs:
            if isinstance(item, ComfyUIInput):
                raw_input = item.raw()
            elif isinstance(item, dict):
                raw_input = dict(item)
            else:
                raise SeaArtError(
                    kind="general",
                    message="inputs must contain ComfyUIInput or dict values",
                )
            field = raw_input.get("field")
            if not isinstance(field, str) or not field.strip():
                raise SeaArtError(kind="general", message="each ComfyUI input requires field")
            if "value" not in raw_input:
                raise SeaArtError(kind="general", message="each ComfyUI input requires value")
            raw_inputs.append(raw_input)

        params: dict[str, object] = {"template_id": template_id, "inputs": raw_inputs}
        if high_memory is not None:
            params["high_memory"] = high_memory
        return self.create({"model": "comfyui", "input": [{"params": params}]}, *options)

    def list_comfyui_templates(
        self,
        template_ids: list[str] | None = None,
        *options: RequestOption,
    ) -> ComfyUITemplateSpecsResponse:
        """Return parameter specifications for the supplied ComfyUI template IDs."""
        body: dict[str, object] = {"type": "comfyui"}
        if template_ids is not None:
            body["template_ids"] = template_ids

        request_options = build_request_options(options)
        status, payload = self._client.request(
            "POST",
            "/v1/template/specs",
            body,
            request_options.headers,
        )
        if status >= 400:
            raise _http_error(status, payload)
        return decode(payload, ComfyUITemplateSpecsResponse)

    def list_models(self, params: ModelSearchParams | None = None, *options: RequestOption) -> ModelSearchResponse:
        """Search multimodal model skills via GET /v1/models/skill/search.

        Supported params:
        - query maps to q
        - input maps to input
        - output maps to output
        - type maps to type
        - provider maps to provider
        - limit maps to limit
        """
        request_options = build_request_options(options)
        status, payload = self._client.request(
            "GET",
            f"/v1/models/skill/search{_model_search_query(params)}",
            None,
            _with_default_header(request_options.headers, "Accept", "application/json"),
        )
        if status >= 400:
            raise _http_error(status, payload)
        return decode(payload, ModelSearchResponse)

    def search_models(self, params: ModelSearchParams | None = None, *options: RequestOption) -> ModelSearchResponse:
        """Search multimodal model skills via GET /v1/models/skill/search.

        Supported params:
        - query maps to q
        - input maps to input
        - output maps to output
        - type maps to type
        - provider maps to provider
        - limit maps to limit
        """
        return self.list_models(params, *options)

    def get_model_skill(self, model: str, *options: RequestOption) -> str:
        model = model.strip()
        if not model:
            raise SeaArtError(kind="general", message="model is required")

        request_options = build_request_options(options)
        status, payload = self._client.request(
            "GET",
            f"/v1/models/skill/{quote(model, safe='')}",
            None,
            _with_default_header(request_options.headers, "Accept", "application/json"),
        )
        if status >= 400:
            raise _http_error(status, payload)
        return payload.decode("utf-8")

    def scan_image(
        self,
        request: ImageScanRequest | dict[str, object],
        *options: RequestOption,
    ) -> ImageScanResponse:
        """Scan an image, GIF, or video through model_base_url + /v1/image/scan."""
        body = request.raw() if isinstance(request, ImageScanRequest) else request
        uri = str(body.get("uri", "")).strip()
        img_base64 = str(body.get("img_base64", "")).strip()
        is_video = bool(body.get("is_video"))
        if not uri and not img_base64:
            raise SeaArtError(kind="general", message="uri or img_base64 is required")
        if uri and img_base64:
            raise SeaArtError(kind="general", message="uri and img_base64 are mutually exclusive")
        if is_video and img_base64:
            raise SeaArtError(kind="general", message="video scans require uri and do not support img_base64")

        request_options = build_request_options(options)
        status, payload = self._client.request(
            "POST",
            "/v1/image/scan",
            body,
            request_options.headers,
        )
        if status >= 400:
            raise _http_error(status, payload)
        return decode(payload, ImageScanResponse)

    def scan_face(
        self,
        request: FaceScanRequest | dict[str, object],
        *options: RequestOption,
    ) -> FaceScanResponse:
        """Scan an image or video through model_base_url + /v1/face/scan."""
        body = request.raw() if isinstance(request, FaceScanRequest) else request
        uri = str(body.get("uri", "")).strip()
        img_base64 = str(body.get("img_base64", "")).strip()
        if not uri and not img_base64:
            raise SeaArtError(kind="general", message="uri or img_base64 is required")

        request_options = build_request_options(options)
        status, payload = self._client.request(
            "POST",
            "/v1/face/scan",
            body,
            request_options.headers,
        )
        if status >= 400:
            raise _http_error(status, payload)
        return decode(payload, FaceScanResponse)

    def scan_text(
        self,
        request: TextScanRequest | dict[str, object],
        *options: RequestOption,
    ) -> TextScanResponse:
        """Scan prompt text through model_base_url + /v1/text/scan."""
        body = request.raw() if isinstance(request, TextScanRequest) else request
        text = str(body.get("text", "")).strip()
        if not text:
            raise SeaArtError(kind="general", message="text is required")

        request_options = build_request_options(options)
        status, payload = self._client.request(
            "POST",
            "/v1/text/scan",
            body,
            request_options.headers,
        )
        if status >= 400:
            raise _http_error(status, payload)
        return decode(payload, TextScanResponse)

    def scan_text_content(
        self,
        request: TextContentScanRequest | dict[str, object],
        *options: RequestOption,
    ) -> TextContentScanResponse:
        """Scan short text through model_base_url + /v1/text/content/scan."""
        body = request.raw() if isinstance(request, TextContentScanRequest) else request
        text = str(body.get("text", "")).strip()
        if not text:
            raise SeaArtError(kind="general", message="text is required")

        request_options = build_request_options(options)
        status, payload = self._client.request(
            "POST",
            "/v1/text/content/scan",
            body,
            request_options.headers,
        )
        if status >= 400:
            raise _http_error(status, payload)
        return decode(payload, TextContentScanResponse)

    def scan_character_quality(
        self,
        request: CharacterQualityScanRequest | dict[str, object],
        *options: RequestOption,
    ) -> CharacterQualityScanResponse:
        """Review character copy quality and safety through /v1/char/quality/scan."""
        body = request.raw() if isinstance(request, CharacterQualityScanRequest) else dict(request)
        if any(not isinstance(value, str) for value in body.values()):
            raise SeaArtError(kind="general", message="character quality scan fields must be strings")

        request_options = build_request_options(options)
        status, payload = self._client.request(
            "POST",
            "/v1/char/quality/scan",
            body,
            request_options.headers,
        )
        if status >= 400:
            raise _http_error(status, payload)
        return decode(payload, CharacterQualityScanResponse)

    def scan_visual_structured_text_fusion(
        self,
        request: VisualStructuredTextFusionScanRequest | dict[str, object],
        *options: RequestOption,
    ) -> VisualStructuredTextFusionScanResponse:
        """Scan a digital-human cover image and structured text together."""
        body = request.raw() if isinstance(request, VisualStructuredTextFusionScanRequest) else request
        text_dict = body.get("text_dict")
        if not isinstance(text_dict, dict) or not text_dict:
            raise SeaArtError(kind="general", message="text_dict is required")
        uri = str(body.get("uri", "")).strip()
        img_base64 = str(body.get("img_base64", "")).strip()
        if not uri and not img_base64:
            raise SeaArtError(kind="general", message="uri or img_base64 is required")

        request_options = build_request_options(options)
        status, payload = self._client.request(
            "POST",
            "/v1/visual/structured/text/fusion/scan",
            body,
            request_options.headers,
        )
        if status >= 400:
            raise _http_error(status, payload)
        return decode(payload, VisualStructuredTextFusionScanResponse)

    def scan_audio(
        self,
        request: AudioScanRequest | dict[str, object],
        *options: RequestOption,
    ) -> AudioScanResponse:
        """Scan audio through model_base_url + /v1/audio/scan."""
        body = request.raw() if isinstance(request, AudioScanRequest) else request
        uri = str(body.get("uri", "")).strip()
        if not uri:
            raise SeaArtError(kind="general", message="uri is required")

        request_options = build_request_options(options)
        status, payload = self._client.request(
            "POST",
            "/v1/audio/scan",
            body,
            request_options.headers,
        )
        if status >= 400:
            raise _http_error(status, payload)
        return decode(payload, AudioScanResponse)

    def get(self, task_id: str, *options: RequestOption) -> Task:
        request_options = build_request_options(options)
        status, payload = self._client.request(
            "GET",
            f"/v1/generation/task/{task_id}",
            None,
            request_options.headers,
        )
        if status >= 400:
            raise _http_error(status, payload)
        task = decode(payload, Task)
        task._service = self
        return task

    def wait(self, task_id: str, *options: PollOption) -> Task:
        config = apply_poll_options(options)
        deadline = time.monotonic() + config.timeout
        network_errors = 0

        while time.monotonic() < deadline:
            try:
                task = self.get(task_id)
            except SeaArtError as exc:
                if exc.kind == ERR_NETWORK and network_errors < POLL_NETWORK_RETRY_LIMIT:
                    network_errors += 1
                    time.sleep(config.interval)
                    continue
                exc.task_id = exc.task_id or task_id
                raise

            network_errors = 0
            status = task.status.lower()
            if config.on_update is not None:
                config.on_update(status, task.progress)

            if status == STATUS_COMPLETED:
                return task
            if status == STATUS_FAILED:
                raise _task_failed_error(task)

            time.sleep(config.interval)

        raise SeaArtError(
            kind=ERR_TIMEOUT,
            message=f"task timed out after {_format_seconds(config.timeout)}",
            task_id=task_id,
        )

    def create_sync(self, body: dict[str, object], *options: RequestOption) -> Task:
        """Create a task and block until it finishes, returning the final result.

        One call instead of ``create`` + ``wait``. The result is identical to what
        :meth:`get` returns once the task is done (including ``usage``).

        The route and the response format are the SDK's business: the caller passes
        the same ``body`` as :meth:`create` and only says "give me the result". The
        SDK uses the gateway's synchronous wait, which is a single ordinary request —
        it keeps working in environments where streaming responses are blocked or
        buffered by a proxy.

        Long tasks: **do not use this method for tasks that may run longer than ~120
        seconds.** That plain request is silent while it waits, so a proxy or load balancer
        can drop it at its idle timeout. Use the asynchronous API instead — :meth:`create`
        returns immediately and :meth:`wait` polls the task with short requests — and reach
        for :meth:`create_stream` only when you want progress or early artifacts. If this call
        reports a timeout, keep polling :meth:`wait` on the returned ``task_id``.

        Raises:
            SeaArtError: ``kind="task_failed"`` when the task itself failed;
                ``kind="timeout"`` when the gateway gave up waiting, with
                ``task_id`` set — resume it with :meth:`subscribe` (or keep polling
                with :meth:`wait`) instead of submitting the work again.
        """
        request_options = build_request_options(options)
        request_body, headers = move_model_to_header(body, request_options.headers)
        headers["Accept"] = ["application/json"]
        status, payload = self._client.request(
            "POST",
            "/v1/generation/sync",
            request_body,
            headers,
        )
        if status >= 400:
            raise _sync_delivery_error(status, payload)
        return _attach_service_and_check(decode(payload, Task), self)

    def create_stream(
        self, body: dict[str, object], *options: RequestOption
    ) -> Iterator[TaskStreamEvent]:
        """Create a task and stream its output as it is produced.

        Yields :class:`TaskStreamEvent` values: ``output`` events carry the chunks
        that arrived (one frame may carry several), the terminal ``done`` event
        carries the complete result, and ``error`` reports a delivery failure or
        timeout. Stop on ``event.done`` — do **not** stop on the ``status`` of a
        chunk frame, which is always ``in_progress``.

        Unlike :meth:`create_sync`, a failed task is reported through the ``done`` event
        (``event.task.status == "failed"``) rather than raised, so callers can
        inspect the payload while iterating.
        """
        request_options = build_request_options(options)
        request_body, headers = move_model_to_header(body, request_options.headers)
        headers["Accept"] = [SSE_CONTENT_TYPE]
        response = self._client.request_stream(
            "POST",
            "/v1/generation/sync",
            request_body,
            headers,
        )
        return _iterate_task_stream(response, self)

    def subscribe(
        self,
        task_id: str,
        cursor: int = 0,
        *options: RequestOption,
    ) -> Iterator[TaskStreamEvent]:
        """Subscribe to an existing task's incremental output.

        Works for running tasks, already finished tasks (chunks replay from
        ``cursor``) and tasks created by someone else. Pass the ``cursor`` of the
        last event you consumed to resume without duplicates — this is what makes
        a dropped streaming connection resumable.
        """
        if not isinstance(task_id, str) or not task_id.strip():
            raise SeaArtError(kind=ERR_GENERAL, message="task_id is required")

        request_options = build_request_options(options)
        headers = {key: list(values) for key, values in request_options.headers.items()}
        headers["Accept"] = [SSE_CONTENT_TYPE]
        path = f"/v1/generation/task/{quote(task_id.strip(), safe='')}/stream"
        if cursor > 0:
            path = f"{path}?cursor={int(cursor)}"
        response = self._client.request_stream("GET", path, None, headers)
        return _iterate_task_stream(response, self)


def _model_search_query(params: ModelSearchParams | None) -> str:
    params = params or ModelSearchParams()
    values: dict[str, str] = {"q": params.query}
    if params.input:
        values["input"] = params.input
    if params.output:
        values["output"] = params.output
    if params.type:
        values["type"] = params.type
    if params.provider:
        values["provider"] = params.provider
    if params.limit > 0:
        values["limit"] = str(params.limit)
    return "?" + urlencode(values)


def _with_default_header(
    headers: dict[str, list[str]],
    key: str,
    value: str,
) -> dict[str, list[str]]:
    if key in headers:
        return headers
    cloned = {name: list(values) for name, values in headers.items()}
    cloned[key] = [value]
    return cloned


def _format_seconds(seconds: float) -> str:
    if seconds.is_integer():
        return f"{int(seconds)}s"
    return f"{seconds}s"


def _http_error(status: int, payload: bytes) -> SeaArtError:
    message = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "HTTP error"
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except Exception:
        return new_http_error(status, message)

    if isinstance(parsed, dict):
        error_payload = parsed.get("error")
        if isinstance(error_payload, dict):
            if error_payload.get("error_message"):
                message = str(error_payload["error_message"])
            elif error_payload.get("message"):
                message = str(error_payload["message"])
    return new_http_error(status, message)


def _json_object(payload: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _attach_service_and_check(task: Task, service: "ModalService") -> Task:
    """Bind the owning service and raise when a synchronous delivery failed."""
    task._service = service
    if task.status.lower() == STATUS_FAILED:
        raise _task_failed_error(task)
    return task


def _task_failed_error(task: Task) -> SeaArtError:
    message = "task failed"
    code: int | str | None = None
    if isinstance(task.error, APIError):
        detail = task.error.error_message or task.error.message
        if detail:
            message = f"task failed: {detail}"
        if task.error.code:
            code = task.error.code
    return SeaArtError(
        kind=ERR_TASK_FAILED,
        message=message,
        task_id=task.id or None,
        code=code,
    )


def _sync_delivery_error(status: int, payload: bytes) -> SeaArtError:
    """Build the error for a failed synchronous delivery.

    Start from the generic HTTP error so the status keeps driving the error kind
    (429 -> quota, 504 -> timeout, ...), then add what only this delivery knows:
    the gateway error code and the task id. A wait timeout answers ``504`` with
    the task id, which callers need in order to keep polling with
    :meth:`ModalService.wait`.
    """
    error = _http_error(status, payload)
    raw = _json_object(payload)
    error_payload = raw.get("error")

    code = ""
    if isinstance(error_payload, dict):
        raw_code = error_payload.get("code")
        if raw_code is not None and str(raw_code):
            code = str(raw_code)
    if code == "SYNC_TIMEOUT":
        error.kind = ERR_TIMEOUT
    if code:
        error.code = code
    if isinstance(raw.get("id"), str) and raw["id"]:
        error.task_id = raw["id"]
    return error


def _iterate_task_stream(response, service: "ModalService") -> Iterator[TaskStreamEvent]:
    """Parse the generation SSE stream into :class:`TaskStreamEvent` values."""
    status = getattr(response, "status", 200)
    if status >= 400:
        payload = response.read()
        response.close()
        raise _sync_delivery_error(status, payload)

    event_name = ""
    data_lines: list[str] = []
    terminal = False
    try:
        while True:
            raw_line = response.readline()
            if raw_line == b"":
                event = _task_stream_event(event_name, data_lines, service)
                if event is not None:
                    terminal = terminal or event.done
                    yield event
                if not terminal:
                    # A stream that ends without a terminal event is a truncated
                    # delivery: the caller must not treat the partial result as
                    # success.
                    raise _stream_ended_early_error()
                return

            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if line == "":
                event = _task_stream_event(event_name, data_lines, service)
                event_name = ""
                data_lines = []
                if event is None:
                    continue
                if event.done:
                    terminal = True
                yield event
                if event.done:
                    return
                continue
            if line.startswith(":"):
                continue  # keepalive comment sent while the task runs
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
    finally:
        response.close()


def _task_stream_event(
    event_name: str, data_lines: list[str], service: "ModalService"
) -> TaskStreamEvent | None:
    if not event_name and not data_lines:
        return None

    data = "\n".join(data_lines).strip()
    if not event_name:
        event_name = "output"
    if data == "[DONE]":
        return TaskStreamEvent(event="done", done=True)

    raw_bytes = data.encode("utf-8")
    raw = _json_object(raw_bytes)
    event = TaskStreamEvent(event=event_name, raw=raw)
    if isinstance(raw.get("id"), str):
        event.task_id = raw["id"]
    if raw.get("status") is not None:
        event.status = str(raw["status"])

    try:
        if event_name == "done":
            task = decode(raw_bytes, Task)
            task._service = service
            event.task = task
            event.done = True
        elif event_name == "error":
            error_payload = raw.get("error")
            if isinstance(error_payload, dict):
                event.error_code = str(error_payload.get("code") or "")
                # The gateway uses ``message`` here, but ``error_message`` also
                # appears on gateway error payloads: keep whichever is present so
                # the failure reason is never dropped.
                message = error_payload.get("message") or error_payload.get("error_message") or ""
                event.error_message = str(message)
            event.done = True
        else:
            frame = decode(raw_bytes, TaskStreamFrame)
            event.cursor = frame.cursor
            event.chunks = frame.output
    except (SeaArtError, ValueError, TypeError) as exc:
        # Surfacing beats swallowing: a malformed frame is reported on the event
        # instead of becoming an empty event, and a raw JSON error never leaks to
        # the caller.
        event.err = (
            exc
            if isinstance(exc, SeaArtError)
            else SeaArtError(kind=ERR_GENERAL, message=f"failed to decode stream frame: {exc}")
        )
    return event


def _stream_ended_early_error() -> SeaArtError:
    return SeaArtError(
        kind=ERR_NETWORK,
        message="stream ended before a terminal event; resume with subscribe(task_id, cursor)",
    )
