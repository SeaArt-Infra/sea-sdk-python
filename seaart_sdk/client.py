from __future__ import annotations

import posixpath
from dataclasses import dataclass
from urllib.parse import urlparse

from .errors import ERR_GENERAL, SeaArtError
from .llm import LLMService
from .modal import ModalService
from .passthrough import PassthroughService
from .transport import TransportClient

DEFAULT_BASE_URL = "https://gateway.example.com"
DEFAULT_MODEL_BASE_URL = DEFAULT_BASE_URL + "/model"
DEFAULT_LLM_BASE_URL = DEFAULT_BASE_URL + "/llm"
DEFAULT_PASSTHROUGH_BASE_URL = DEFAULT_MODEL_BASE_URL
DEFAULT_TIMEOUT = 300.0
SDK_VERSION = "0.1.0"


@dataclass(slots=True)
class ClientConfig:
    api_key: str = ""
    base_url: str = ""
    model_base_url: str = ""
    llm_base_url: str = ""
    passthrough_base_url: str = ""
    project: str = ""
    timeout: float = DEFAULT_TIMEOUT


class Client:
    def __init__(self, config: ClientConfig | None = None) -> None:
        config = config or ClientConfig()
        base_url = _resolve_root_url(config.base_url)
        model_base_url = _resolve_service_url(
            config.model_base_url,
            derive_from_root=bool(config.base_url),
            root=base_url,
            suffix="model",
            fallback=DEFAULT_MODEL_BASE_URL,
        )
        llm_base_url = _resolve_service_url(
            config.llm_base_url,
            derive_from_root=bool(config.base_url),
            root=base_url,
            suffix="llm",
            fallback=DEFAULT_LLM_BASE_URL,
        )
        passthrough_base_url = _resolve_passthrough_url(
            config.passthrough_base_url,
            model_base_url,
        )

        timeout = config.timeout if config.timeout > 0 else DEFAULT_TIMEOUT
        self.api_key = config.api_key
        self.base_url = base_url
        self.model_base_url = model_base_url
        self.llm_base_url = llm_base_url
        self.passthrough_base_url = passthrough_base_url
        self.project = config.project

        modal_transport = TransportClient(
            api_key=self.api_key,
            base_url=self.model_base_url,
            project=self.project,
            user_agent=f"sa-python/{SDK_VERSION}",
            timeout=timeout,
        )
        llm_transport = TransportClient(
            api_key=self.api_key,
            base_url=self.llm_base_url,
            project=self.project,
            user_agent=f"sa-python/{SDK_VERSION}",
            timeout=timeout,
        )
        passthrough_transport = TransportClient(
            api_key=self.api_key,
            base_url=self.passthrough_base_url,
            project=self.project,
            user_agent=f"sa-python/{SDK_VERSION}",
            timeout=timeout,
        )

        self.modal = ModalService(modal_transport)
        self.llm = LLMService(llm_transport)
        self.passthrough = PassthroughService(passthrough_transport)

        self.Modal = self.modal
        self.LLM = self.llm
        self.Passthrough = self.passthrough


def new(config: ClientConfig | None = None) -> Client:
    return Client(config)


def _resolve_root_url(raw: str) -> str:
    return _normalize_url(raw or DEFAULT_BASE_URL)


def _resolve_service_url(
    raw: str,
    *,
    derive_from_root: bool,
    root: str,
    suffix: str,
    fallback: str,
) -> str:
    if raw:
        return _normalize_url(raw)
    if derive_from_root:
        return _join_url(root, suffix)
    return fallback


def _resolve_passthrough_url(raw: str, model_base_url: str) -> str:
    if raw:
        return _normalize_url(raw)
    return model_base_url


def _normalize_url(raw: str) -> str:
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise SeaArtError(kind=ERR_GENERAL, message="invalid URL: missing scheme or host")

    normalized_path = posixpath.normpath(parsed.path or "/")
    if normalized_path == "/":
        normalized_path = ""

    return parsed._replace(path=normalized_path).geturl()


def _join_url(base_url: str, suffix: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise SeaArtError(kind=ERR_GENERAL, message="invalid URL: missing scheme or host")

    joined_path = posixpath.join(parsed.path or "/", suffix)
    return _normalize_url(parsed._replace(path=joined_path).geturl())
