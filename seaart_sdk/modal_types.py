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
    input: list[InputItem] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)

    def raw(self) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.model}
        if self.input:
            body["input"] = [_raw_input(item) for item in self.input]
        if self.parameters:
            body["parameters"] = self.parameters
        if self.metadata:
            body["metadata"] = self.metadata
        if self.options:
            body["options"] = self.options
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

    def input(self, item: InputItem) -> "TaskBuilder":
        return self.input_item(item)

    def input_item(self, item: InputItem) -> "TaskBuilder":
        self.request.input.append(item)
        return self

    def user(self, *parts: ContentPart) -> "TaskBuilder":
        self.request.input.append(user(*parts))
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


def user(*parts: ContentPart) -> InputItem:
    return InputItem(type="message", role="user", content=list(parts))


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
