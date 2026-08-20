from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BillingQuery:
    start: str = ""
    end: str = ""
    environment: str = ""
    provider: str = ""
    credential_name: str = ""
    model_group: str = ""
    page: int = 0
    page_size: int = 0

    def query_params(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for key in ("start", "end", "environment", "provider", "credential_name", "model_group"):
            value = getattr(self, key)
            if value:
                values[key] = str(value)
        if self.page > 0:
            values["page"] = str(self.page)
        if self.page_size > 0:
            values["page_size"] = str(self.page_size)
        return values


@dataclass(slots=True)
class BillingSummary:
    total_requests: int = 0
    total_cost: str = ""
    discount_total_cost: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    currency: str = ""


@dataclass(slots=True)
class BillingItem:
    team_alias: str = ""
    provider: str = ""
    model_group: str = ""
    total_requests: int = 0
    total_cost: str = ""
    discount_total_cost: str = ""
    discount_rate: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(slots=True)
class BillingPage:
    items: list[BillingItem] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


@dataclass(slots=True)
class BillingResponse:
    team: str = ""
    environments: list[str] = field(default_factory=list)
    summary: BillingSummary = field(default_factory=BillingSummary)
    items: BillingPage = field(default_factory=BillingPage)
    extra: dict[str, Any] = field(default_factory=dict)
