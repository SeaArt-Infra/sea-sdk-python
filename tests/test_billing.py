from __future__ import annotations

import unittest

from seaart_sdk import BillingQuery, BillingResponse, Client, ClientConfig, SeaArtError
from tests.test_helpers import json_response, patch_urlopen, request_headers, request_path


class BillingServiceTests(unittest.TestCase):
    def test_query_builds_scoped_billing_request(self) -> None:
        client = Client(ClientConfig(api_key="test-key", billing_base_url="https://billing.example.com"))

        def handler(request):
            self.assertEqual(request.method, "GET")
            self.assertEqual(request_path(request), "/api/v1/cost/billing")
            self.assertEqual(request.full_url.split("?", 1)[1], "start=2026-08-19T00%3A00%3A00Z&environment=release&model_group=seedream&page=2&page_size=10")
            self.assertEqual(request_headers(request)["Authorization"], "Bearer test-key")
            return json_response(200, {"code": 0, "message": "ok", "data": {
                "team": "SeaComfyui",
                "environments": ["release"],
                "summary": {"total_requests": 3, "total_cost": "1.25", "currency": "USD"},
                "items": {"items": [{"team_alias": "SeaComfyui", "provider": "p", "model_group": "seedream", "total_cost": "1.25"}], "total": 1, "page": 2, "page_size": 10, "total_pages": 1},
            }})

        with patch_urlopen(handler):
            response = client.billing.query(BillingQuery(
                start="2026-08-19T00:00:00Z", environment="release", model_group="seedream", page=2, page_size=10,
            ))

        self.assertIsInstance(response, BillingResponse)
        self.assertEqual(response.team, "SeaComfyui")
        self.assertEqual(response.summary.total_cost, "1.25")
        self.assertEqual(response.items.items[0].model_group, "seedream")

    def test_query_accepts_mapping_and_surfaces_envelope_errors(self) -> None:
        client = Client(ClientConfig(api_key="test-key", billing_base_url="https://billing.example.com"))

        with patch_urlopen(lambda request: json_response(400, {"code": 400, "message": "X-User-ID header is required"})):
            with self.assertRaises(SeaArtError) as context:
                client.billing.get({"environment": "develop"})

        self.assertEqual(context.exception.status, 400)
        self.assertEqual(context.exception.message, "X-User-ID header is required")


if __name__ == "__main__":
    unittest.main()
