from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.parse import urlencode

from .errors import ERR_GENERAL, SeaArtError, new_http_error
from .request_options import RequestOption, build_request_options
from .serialization import decode
from .transport import TransportClient
from .billing_types import BillingQuery, BillingResponse

PATH_BILLING = "/api/v1/cost/billing"


class BillingService:
    def __init__(self, client: TransportClient) -> None:
        self._client = client

    def query(
        self,
        params: BillingQuery | Mapping[str, object] | None = None,
        *options: RequestOption,
    ) -> BillingResponse:
        query = _query_params(params)
        suffix = f"?{urlencode(query)}" if query else ""
        request_options = build_request_options(options)
        status, payload = self._client.request("GET", PATH_BILLING + suffix, None, request_options.headers)
        if status >= 400:
            raise _http_error(status, payload)
        try:
            envelope = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SeaArtError(kind=ERR_GENERAL, message=f"failed to decode response: {exc}") from exc
        if envelope.get("code", 0) != 0:
            raise SeaArtError(
                kind=ERR_GENERAL,
                status=status,
                code=envelope.get("code"),
                message=str(envelope.get("message") or "billing query failed"),
            )
        return decode(envelope.get("data") or {}, BillingResponse)

    def get(self, params: BillingQuery | Mapping[str, object] | None = None, *options: RequestOption) -> BillingResponse:
        return self.query(params, *options)


def _query_params(params: BillingQuery | Mapping[str, object] | None) -> dict[str, str]:
    if params is None:
        return {}
    if isinstance(params, BillingQuery):
        return params.query_params()
    if not isinstance(params, Mapping):
        raise SeaArtError(kind=ERR_GENERAL, message="billing params must be BillingQuery or mapping")
    allowed = ("start", "end", "environment", "provider", "credential_name", "model_group")
    result = {key: str(params[key]) for key in allowed if params.get(key) not in (None, "")}
    for key in ("page", "page_size"):
        if params.get(key) not in (None, "", 0):
            result[key] = str(params[key])
    return result


def _http_error(status: int, payload: bytes) -> SeaArtError:
    message = f"HTTP {status}"
    try:
        body = json.loads(payload.decode("utf-8"))
        message = str(body.get("message") or body.get("error", {}).get("message") or message)
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        pass
    return new_http_error(status, message)
