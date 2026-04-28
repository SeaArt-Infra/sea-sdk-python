from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JSONMap = dict[str, Any]
RawResponse = bytes


@dataclass(slots=True)
class StreamEvent:
    event: str = ""
    data: RawResponse | None = None
    done: bool = False
    err: Exception | None = None


@dataclass(slots=True)
class LLMMessage:
    role: str = ""
    content: Any = None
    name: str = ""
    tool_call_id: str = ""
    tool_calls: list["LLMToolCall"] = field(default_factory=list)


@dataclass(slots=True)
class LLMToolCall:
    id: str = ""
    type: str = ""
    function: "LLMFunctionCall | None" = None


@dataclass(slots=True)
class LLMFunctionCall:
    name: str = ""
    arguments: str = ""


@dataclass(slots=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass(slots=True)
class ChatCompletionChoice:
    index: int = 0
    message: LLMMessage | None = None
    delta: LLMMessage | None = None
    finish_reason: str = ""


@dataclass(slots=True)
class ChatCompletionResponse:
    id: str = ""
    object: str = ""
    created: int = 0
    model: str = ""
    choices: list[ChatCompletionChoice] = field(default_factory=list)
    usage: LLMUsage | None = None


@dataclass(slots=True)
class MessagesContentBlock:
    type: str = ""
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    source: Any = None


@dataclass(slots=True)
class MessagesResponse:
    id: str = ""
    type: str = ""
    role: str = ""
    model: str = ""
    content: list[MessagesContentBlock] = field(default_factory=list)
    stop_reason: str = ""
    choices: list[ChatCompletionChoice] = field(default_factory=list)
    usage: LLMUsage | None = None


@dataclass(slots=True)
class MessagesStreamMessage:
    id: str = ""
    type: str = ""
    role: str = ""
    model: str = ""
    content: list[MessagesContentBlock] = field(default_factory=list)
    stop_reason: str = ""
    stop_sequence: Any = None
    usage: LLMUsage | None = None


@dataclass(slots=True)
class MessagesStreamContentBlock:
    type: str = ""
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    source: Any = None
    partial_json: str = ""
    thinking: str = ""
    signature: str = ""


@dataclass(slots=True)
class MessagesStreamDelta:
    type: str = ""
    text: str = ""
    partial_json: str = ""
    thinking: str = ""
    signature: str = ""
    stop_reason: str = ""
    stop_sequence: Any = None


@dataclass(slots=True)
class MessagesStreamChunk:
    type: str = ""
    index: int = 0
    message: MessagesStreamMessage | None = None
    content_block: MessagesStreamContentBlock | None = None
    delta: MessagesStreamDelta | None = None
    usage: LLMUsage | None = None

    def text_delta(self) -> str:
        if self.delta and self.delta.type == "text_delta":
            return self.delta.text
        return ""

    def thinking_delta(self) -> str:
        if self.delta and self.delta.type == "thinking_delta":
            return self.delta.thinking
        return ""

    def input_json_delta(self) -> str:
        if self.delta and self.delta.type == "input_json_delta":
            return self.delta.partial_json
        return ""


@dataclass(slots=True)
class MessagesStreamTextAssembler:
    chunks: list[str] = field(default_factory=list)

    def add(self, chunk: MessagesStreamChunk | None) -> None:
        if chunk is None:
            return
        text = chunk.text_delta()
        if text:
            self.chunks.append(text)

    def text(self) -> str:
        return "".join(self.chunks)


@dataclass(slots=True)
class ResponsesContentItem:
    type: str = ""
    text: str = ""
    annotations: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ResponsesOutputItem:
    id: str = ""
    type: str = ""
    status: str = ""
    role: str = ""
    name: str = ""
    call_id: str = ""
    arguments: str = ""
    content: list[ResponsesContentItem] = field(default_factory=list)


@dataclass(slots=True)
class ResponsesResponse:
    id: str = ""
    object: str = ""
    model: str = ""
    status: str = ""
    output: list[ResponsesOutputItem] = field(default_factory=list)
    choices: list[ChatCompletionChoice] = field(default_factory=list)
    usage: LLMUsage | None = None


@dataclass(slots=True)
class ResponsesStreamContentPart:
    type: str = ""
    text: str = ""
    annotations: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ResponsesStreamOutputItem:
    id: str = ""
    type: str = ""
    status: str = ""
    role: str = ""
    name: str = ""
    call_id: str = ""
    arguments: str = ""
    output: str = ""
    content: list[ResponsesStreamContentPart] = field(default_factory=list)


@dataclass(slots=True)
class ResponsesResponseStreamChunk:
    type: str = ""
    sequence_number: int = 0
    response_id: str = ""
    output_index: int = 0
    content_index: int = 0
    item_id: str = ""
    response: ResponsesResponse | None = None
    item: ResponsesStreamOutputItem | None = None
    part: ResponsesStreamContentPart | None = None
    delta: str = ""
    text: str = ""
    annotation: dict[str, Any] = field(default_factory=dict)
    error: Any = None

    def text_delta(self) -> str:
        if self.type == "response.output_text.delta":
            return self.delta
        return ""

    def output_text(self) -> str:
        if self.type == "response.output_text.done":
            return self.text
        if self.type in {"response.content_part.added", "response.content_part.done"} and self.part:
            if self.part.type == "output_text":
                return self.part.text
        return ""


@dataclass(slots=True)
class ResponsesStreamTextAssembler:
    chunks: list[str] = field(default_factory=list)

    def add(self, chunk: ResponsesResponseStreamChunk | None) -> None:
        if chunk is None:
            return
        text = chunk.text_delta()
        if text:
            self.chunks.append(text)

    def text(self) -> str:
        return "".join(self.chunks)


@dataclass(slots=True)
class RerankResult:
    index: int = 0
    relevance_score: float = 0.0
    document: Any = None


@dataclass(slots=True)
class RerankBilledUnits:
    search_units: int = 0
    total_tokens: int = 0


@dataclass(slots=True)
class RerankTokens:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(slots=True)
class RerankResponseMeta:
    api_version: JSONMap = field(default_factory=dict)
    billed_units: RerankBilledUnits | None = None
    tokens: RerankTokens | None = None


@dataclass(slots=True)
class RerankUsage:
    total_tokens: int = 0


@dataclass(slots=True)
class RerankResponse:
    id: str = ""
    results: list[RerankResult] = field(default_factory=list)
    meta: RerankResponseMeta | None = None
    usage: RerankUsage | None = None


@dataclass(slots=True)
class EmbeddingObject:
    object: str = ""
    index: int = 0
    embedding: Any = None


@dataclass(slots=True)
class EmbeddingsResponse:
    object: str = ""
    data: list[EmbeddingObject] = field(default_factory=list)
    model: str = ""
    usage: LLMUsage | None = None


@dataclass(slots=True)
class LLMModel:
    id: str = ""
    object: str = ""
    created: int = 0
    owned_by: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LLMModelListResponse:
    object: str = ""
    data: list[LLMModel] = field(default_factory=list)
