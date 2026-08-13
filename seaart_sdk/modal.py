from __future__ import annotations

import json
import time
from http import HTTPStatus
from urllib.parse import quote, urlencode

from .errors import ERR_NETWORK, ERR_TASK_FAILED, ERR_TIMEOUT, SeaArtError, new_http_error
from .modal_types import (
    APIError,
    AudioScanRequest,
    AudioScanResponse,
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
                message = "task failed"
                code: int | None = None
                if isinstance(task.error, APIError):
                    detail = task.error.error_message or task.error.message
                    if detail:
                        message = f"task failed: {detail}"
                    if task.error.code:
                        code = task.error.code
                raise SeaArtError(kind=ERR_TASK_FAILED, message=message, task_id=task_id, code=code)

            time.sleep(config.interval)

        raise SeaArtError(
            kind=ERR_TIMEOUT,
            message=f"task timed out after {_format_seconds(config.timeout)}",
            task_id=task_id,
        )


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
