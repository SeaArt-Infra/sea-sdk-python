from __future__ import annotations

from dataclasses import dataclass

ERR_AUTH = "auth"
ERR_QUOTA = "quota"
ERR_TIMEOUT = "timeout"
ERR_NETWORK = "network"
ERR_TASK_FAILED = "task_failed"
ERR_GENERAL = "general"


@dataclass(eq=False)
class SeaArtError(Exception):
    kind: str
    message: str
    status: int | None = None
    task_id: str | None = None
    code: int | str | None = None

    def __str__(self) -> str:
        if self.task_id:
            return f"{self.message} (task_id: {self.task_id})"
        return self.message


def new_http_error(status: int, message: str) -> SeaArtError:
    kind = ERR_GENERAL
    if status in (401, 403):
        kind = ERR_AUTH
    elif status == 429:
        kind = ERR_QUOTA
    elif status in (408, 504):
        kind = ERR_TIMEOUT
    return SeaArtError(kind=kind, status=status, message=message)
