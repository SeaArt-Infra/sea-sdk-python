from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .errors import ERR_GENERAL, SeaArtError


@dataclass(slots=True)
class APIError:
    code: int = 0
    error_message: str = ""

    def __str__(self) -> str:
        return self.error_message or "unknown API error"


RiskType = str
"""Image scan risk category value used in request risk_types and response risk_types."""


TextScanAreaType = int
"""Text scan regional rule-set selector used in request area_types."""

TextScanWay = int
"""Text scan checking strategy value used in request way."""


# Political or public-safety sensitive content.
IMAGE_SCAN_RISK_TYPE_POLITY = "POLITY"
# Erotic, pornographic, nudity, or sexually suggestive content.
IMAGE_SCAN_RISK_TYPE_EROTIC = "EROTIC"
# Violent, bloody, weapon, or gore-related content.
IMAGE_SCAN_RISK_TYPE_VIOLENT = "VIOLENT"
# Child-safety risks, especially sexualized or unsafe child-related content.
IMAGE_SCAN_RISK_TYPE_CHILD = "CHILD"

# Check both domestic and foreign regional sensitive-word rule sets.
TEXT_SCAN_AREA_TYPE_ALL = 0
# Check the domestic regional sensitive-word rule set.
TEXT_SCAN_AREA_TYPE_DOMESTIC = 1
# Check the foreign regional sensitive-word rule set.
TEXT_SCAN_AREA_TYPE_FOREIGN = 2

# Use dictionary matching. This is the upstream default.
TEXT_SCAN_WAY_DICTIONARY = 0
# Use the big-data model checker.
TEXT_SCAN_WAY_MODEL = 1
# Use both dictionary and model checks.
TEXT_SCAN_WAY_MIXED = 2
# Use the digital-human checker.
TEXT_SCAN_WAY_CHARACTER = 3


@dataclass(slots=True)
class OutputContent:
    job_id: str = field(default="", metadata={"json": "jobId"})
    type: str = ""
    url: str = ""


@dataclass(slots=True)
class Output:
    content: list[OutputContent] = field(default_factory=list)


@dataclass(slots=True)
class Usage:
    cost: float | str | int | None = None
    discount: float = 0.0
    used: int | None = None
    model_batch_uuid: str = ""
    time_per_unit: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def cost_float64(self) -> float:
        if self.cost is None:
            return 0.0
        return float(self.cost)


@dataclass(slots=True)
class ImageScanRequest:
    """Request body for POST /v1/image/scan.

    Attributes:
        uri: Image, GIF, or video URL to scan.
        risk_types: Safety categories to detect. Use ImageScanRiskTypePolity,
            ImageScanRiskTypeErotic, ImageScanRiskTypeViolent, and/or ImageScanRiskTypeChild.
        detected_age: Set to 1 to enable age-group detection; set to 0 to disable it.
        is_video: Set to 1 when uri points to video content; images and GIFs use 0.
        duration: Video duration in seconds, used for video billing when known.
    """

    uri: str
    risk_types: list[RiskType] = field(default_factory=list)
    detected_age: int = 0
    is_video: int = 0
    duration: float = 0.0

    def raw(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "uri": self.uri,
            "risk_types": self.risk_types,
            "detected_age": self.detected_age,
            "is_video": self.is_video,
        }
        if self.duration:
            body["duration"] = self.duration
        return body


@dataclass(slots=True)
class ImageScanLabel:
    """Detailed safety label detected by the scan service.

    Attributes:
        name: Provider label name, for example a scene/category/tag path.
        score: Label risk score or level, usually aligned to the 0-6 risk scale.
        risk_type: Safety category this label belongs to.
    """

    name: str = ""
    score: int = 0
    risk_type: RiskType = ""


@dataclass(slots=True)
class ImageScanFrameResult:
    """Per-frame result for video scans.

    Attributes:
        frame_index: Sampled frame index in the video.
        nsfw_level: Highest risk level detected on this frame.
        label_items: Detailed labels detected on this frame.
        risk_types: Risk categories detected on this frame.
    """

    frame_index: int = 0
    nsfw_level: int = 0
    label_items: list[ImageScanLabel] = field(default_factory=list)
    risk_types: list[RiskType] = field(default_factory=list)


@dataclass(slots=True)
class ImageScanResponse:
    """Parsed response returned by POST /v1/image/scan.

    Attributes:
        ok: Whether the scan service completed the business request successfully.
        nsfw_level: Highest risk level, usually 0-6. Higher values indicate higher risk.
        label_items: Detailed labels detected on image content or the highest-risk frame.
        risk_types: Risk categories actually detected in the media.
        age_group: Provider-specific age-group output, typically age bucket and confidence.
        error: Scan service business error when ok is false.
        video_duration: Duration detected or used by the upstream video scanner, in seconds.
        max_risk_frame: Frame index with the highest risk in a video scan.
        frame_count: Total number of frames sampled or considered by the scanner.
        frames_checked: Actual number of frames scanned before completion or early exit.
        early_exit: Whether the scanner stopped early after finding a high-risk frame.
        frame_results: Per-frame results for video scans.
        usage: Gateway billing metadata injected by inference-gateway.
    """

    ok: bool = False
    nsfw_level: int = 0
    label_items: list[ImageScanLabel] = field(default_factory=list)
    risk_types: list[RiskType] = field(default_factory=list)
    age_group: list[Any] = field(default_factory=list)
    error: str = ""
    video_duration: float = 0.0
    max_risk_frame: int = 0
    frame_count: int = 0
    frames_checked: int = 0
    early_exit: bool = False
    frame_results: list[ImageScanFrameResult] = field(default_factory=list)
    usage: Usage | None = None


@dataclass(slots=True)
class TextScanRequest:
    """Request body for POST /v1/text/scan.

    Attributes:
        text: Prompt or text content to scan for sensitive words.
        scene: Upstream moderation scenario, for example 1 for search sensitive
            words and 2 for prompt sensitive words.
        area_types: Regional rule sets to check. 0 checks both domestic and
            foreign rules, 1 checks domestic rules, and 2 checks foreign rules.
        way: Checking strategy. 0 uses dictionary matching, 1 uses the big-data
            model checker, 2 uses mixed checks, and 3 uses the digital-human checker.
        scenes: Currently unused by the upstream service. When provided, it
            overrides scene.
    """

    text: str
    scene: int = 0
    area_types: list[TextScanAreaType] = field(default_factory=list)
    way: TextScanWay = 0
    scenes: list[str] = field(default_factory=list)

    def raw(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "text": self.text,
            "scene": self.scene,
        }
        if self.area_types:
            body["area_types"] = self.area_types
        body["way"] = self.way
        if self.scenes:
            body["scenes"] = self.scenes
        return body


@dataclass(slots=True)
class TextScanSensitiveWord:
    """One sensitive-word match returned by POST /v1/text/scan.

    Attributes:
        word: Matched sensitive word.
        start_index: Rune-array start index of the matched word.
        end_index: Rune-array end index of the matched word.
        risk_type_code: Upstream risk category, for example political,
            violence, or porn.
    """

    word: str = ""
    start_index: int = 0
    end_index: int = 0
    risk_type_code: str = ""


@dataclass(slots=True)
class TextScanData:
    """Text moderation results returned by POST /v1/text/scan.

    Attributes:
        sensitive_words: Every sensitive word matched by the service.
        combination: Upstream combination-rule details when a match is produced.
        is_sensitive: Whether the scanned text matched sensitive content.
    """

    sensitive_words: list[TextScanSensitiveWord] = field(default_factory=list)
    combination: Any = None
    is_sensitive: bool = False


@dataclass(slots=True)
class TextScanStatus:
    """Upstream business status returned by POST /v1/text/scan."""

    code: int = 0
    msg: str = ""
    request_id: str = ""


@dataclass(slots=True)
class TextScanResponse:
    """Parsed response returned by POST /v1/text/scan.

    Extra keeps upstream response fields that are not modeled by the SDK yet.
    """

    data: TextScanData | None = None
    status: TextScanStatus | None = None
    usage: Usage | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FaceScanRequest:
    """Request body for POST /v1/face/scan.

    Attributes:
        uri: Image or video URL to scan.
        img_base64: Base64-encoded image payload. uri or img_base64 is required.
        is_video: Set to 1 when uri points to video content; images use 0.
        canary: Canary routing value forwarded to the upstream face scan service.
        scene: Scenario value forwarded to the upstream face scan service.
        duration: Video duration in seconds, used for video billing when known.
    """

    uri: str = ""
    img_base64: str = ""
    is_video: int = 0
    canary: str = ""
    scene: str = ""
    duration: float = 0.0

    def raw(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "is_video": self.is_video,
        }
        if self.uri:
            body["uri"] = self.uri
        if self.img_base64:
            body["img_base64"] = self.img_base64
        if self.canary:
            body["canary"] = self.canary
        if self.scene:
            body["scene"] = self.scene
        if self.duration:
            body["duration"] = self.duration
        return body


@dataclass(slots=True)
class FaceScanResponse:
    """Parsed response returned by POST /v1/face/scan.

    The upstream face scan service owns most response fields, so extra keeps
    provider-specific fields available while usage is decoded for gateway billing.
    """

    ok: bool = False
    error: str = ""
    usage: Usage | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TaskMetadata:
    completed_at: float = 0.0
    in_queue_at: float = 0.0
    upload_at: float = 0.0


@dataclass(slots=True)
class GenerationResponse:
    id: str = ""
    created_at: int = 0
    status: str = ""
    model: str = ""
    error: APIError | None = None


@dataclass(slots=True)
class PrechargeData:
    billing_model: str = ""
    cost: str | None = None
    currency: str = ""
    discount: float = 0.0
    hash: str = ""
    model: str = ""
    original_model: str = ""
    sample_count: int = 0
    updated_at: int = 0
    reason: str = ""


@dataclass(slots=True)
class PrechargeResponse:
    data: PrechargeData | None = None
    status: str = ""


@dataclass(slots=True)
class Task:
    id: str = ""
    status: str = ""
    model: str = ""
    progress: float = 0.0
    output: list[Output] = field(default_factory=list)
    usage: Usage | None = None
    metadata: TaskMetadata | None = None
    error: APIError | None = None
    _service: Any = field(default=None, repr=False, compare=False)

    def wait(self, *options: "PollOption") -> "Task":
        if self._service is None:
            raise SeaArtError(kind=ERR_GENERAL, message="task is detached from client")
        return self._service.wait(self.id, *options)

    def urls(self) -> list[str]:
        urls: list[str] = []
        for item in self.output:
            for content in item.content:
                if content.url:
                    urls.append(content.url)
        return urls


@dataclass(slots=True)
class ModelSearchParams:
    query: str = ""
    input: str = ""
    output: str = ""
    type: str = ""
    provider: str = ""
    limit: int = 0


@dataclass(slots=True)
class ModelSearchResponse:
    hits: list[dict[str, Any]] = field(default_factory=list)
    query: str = ""
    processing_time_ms: int = field(default=0, metadata={"json": "processingTimeMs"})
    limit: int = 0
    offset: int = 0
    estimated_total_hits: int = field(default=0, metadata={"json": "estimatedTotalHits"})
    total_hits: int = field(default=0, metadata={"json": "totalHits"})
    total_pages: int = field(default=0, metadata={"json": "totalPages"})
    page: int = 0
    hits_per_page: int = field(default=0, metadata={"json": "hitsPerPage"})


@dataclass(slots=True)
class ContentPart:
    type: str
    text: str = ""
    url: str = ""
    file_id: str = ""
    mime: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InputItem:
    type: str = ""
    role: str = ""
    text: str = ""
    url: str = ""
    file_id: str = ""
    mime: str = ""
    content: list[ContentPart] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TaskCreateRequest:
    model: str
    params: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)
    moderation: bool | None = None
    extra_top_level: dict[str, Any] = field(default_factory=dict)

    def raw(self) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.model}
        if self.moderation is not None:
            body["moderation"] = self.moderation
        params = dict(self.params)
        if self.parameters:
            existing_parameters = params.get("parameters")
            if isinstance(existing_parameters, dict):
                params["parameters"] = {**existing_parameters, **self.parameters}
            else:
                params["parameters"] = self.parameters
        if params:
            body["input"] = [{"params": params}]
        if self.metadata:
            body["metadata"] = self.metadata
        if self.options:
            body["options"] = self.options
        if self.extra_top_level:
            body.update(self.extra_top_level)
        return body


def _raw_input(item: InputItem) -> dict[str, Any]:
    entry: dict[str, Any] = {}
    if item.type:
        entry["type"] = item.type
    if item.role:
        entry["role"] = item.role
    if item.text:
        entry["text"] = item.text
    if item.url:
        entry["url"] = item.url
    if item.file_id:
        entry["file_id"] = item.file_id
    if item.mime:
        entry["mime"] = item.mime
    if item.content:
        entry["content"] = [_raw_part(part) for part in item.content]
    if item.extra:
        entry["extra"] = item.extra
    return entry


def _raw_part(part: ContentPart) -> dict[str, Any]:
    entry: dict[str, Any] = {"type": part.type}
    if part.text:
        entry["text"] = part.text
    if part.url:
        entry["url"] = part.url
    if part.file_id:
        entry["file_id"] = part.file_id
    if part.mime:
        entry["mime"] = part.mime
    if part.extra:
        entry["extra"] = part.extra
    return entry


@dataclass(slots=True)
class TaskBuilder:
    request: TaskCreateRequest

    def params(self, value: dict[str, Any]) -> "TaskBuilder":
        self.request.params = dict(value)
        return self

    def param(self, key: str, value: Any) -> "TaskBuilder":
        self.request.parameters[key] = value
        return self

    def metadata(self, key: str, value: Any) -> "TaskBuilder":
        return self.metadata_item(key, value)

    def metadata_item(self, key: str, value: Any) -> "TaskBuilder":
        self.request.metadata[key] = value
        return self

    def option(self, key: str, value: Any) -> "TaskBuilder":
        self.request.options[key] = value
        return self

    def moderation(self, value: bool) -> "TaskBuilder":
        self.request.moderation = value
        return self

    def field(self, key: str, value: Any) -> "TaskBuilder":
        self.request.extra_top_level[key] = value
        return self

    def build(self) -> dict[str, Any]:
        return self.request.raw()


def new_task(model: str) -> TaskBuilder:
    return TaskBuilder(
        request=TaskCreateRequest(
            model=model,
            parameters={},
            metadata={},
            options={},
        )
    )


def text(value: str) -> ContentPart:
    return ContentPart(type="text", text=value)


def image_url(url: str) -> ContentPart:
    return ContentPart(type="image_url", url=url)


def video_url(url: str) -> ContentPart:
    return ContentPart(type="video_url", url=url)


def audio_url(url: str) -> ContentPart:
    return ContentPart(type="audio_url", url=url)


def file_id(value: str) -> ContentPart:
    return ContentPart(type="file_id", file_id=value)


@dataclass(slots=True)
class PollConfig:
    interval: float = 3.0
    timeout: float = 300.0
    on_update: Callable[[str, float], None] | None = None


PollOption = Callable[[PollConfig], None]


def with_poll_interval(seconds: float) -> PollOption:
    def apply(config: PollConfig) -> None:
        config.interval = seconds

    return apply


def with_poll_timeout(seconds: float) -> PollOption:
    def apply(config: PollConfig) -> None:
        config.timeout = seconds

    return apply


def with_poll_callback(callback: Callable[[str, float], None]) -> PollOption:
    def apply(config: PollConfig) -> None:
        config.on_update = callback

    return apply


def apply_poll_options(options: tuple[PollOption, ...]) -> PollConfig:
    config = PollConfig()
    for option in options:
        if option is not None:
            option(config)
    return config
