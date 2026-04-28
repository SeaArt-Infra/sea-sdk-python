from __future__ import annotations

import json
import unittest

from seaart_sdk import SeaArtError, with_header

from test_helpers import (
    FakeResponse,
    json_response,
    make_client,
    patch_urlopen,
    request_body,
    request_headers,
    request_json,
    request_path,
)


class PassthroughServiceTests(unittest.TestCase):
    def test_post_uses_model_base_url(self) -> None:
        def handler(request) -> FakeResponse:
            self.assertEqual(request.full_url, "https://modal.example.com/kling/v1/videos/text2video")
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/kling/v1/videos/text2video")
            self.assertEqual(request_headers(request)["Authorization"], "Bearer test-key")
            self.assertEqual(request_headers(request)["X-trace-id"], "trace-123")
            self.assertEqual(request_json(request)["model_name"], "kling-v1")
            return json_response(202, {"data": {"task_id": "task_123"}})

        with patch_urlopen(handler):
            response = make_client().passthrough.post(
                "/kling/v1/videos/text2video",
                {"model_name": "kling-v1"},
                with_header("X-Trace-Id", "trace-123"),
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(json.loads(response.body.decode("utf-8"))["data"]["task_id"], "task_123")

    def test_request_raw_sends_body_as_is(self) -> None:
        raw_body = b'{"contents":[{"parts":[{"text":"paint a cat"}]}]}'

        def handler(request) -> FakeResponse:
            self.assertEqual(
                request_path(request),
                "/google/v1beta/models/gemini-2.5-flash-image:generateContent",
            )
            self.assertEqual(request_body(request), raw_body)
            return json_response(200, {"ok": True})

        with patch_urlopen(handler):
            response = make_client().passthrough.request_raw(
                "POST",
                "google/v1beta/models/gemini-2.5-flash-image:generateContent",
                raw_body,
            )

        self.assertEqual(response.status_code, 200)

    def test_http_error_status_returns_response_body(self) -> None:
        def handler(request) -> FakeResponse:
            return json_response(400, {"error": {"message": "bad request"}})

        with patch_urlopen(handler):
            response = make_client().passthrough.get("/vidu/v2/tasks/task_123/creations")

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"bad request", response.body)

    def test_rejects_absolute_url(self) -> None:
        with self.assertRaises(SeaArtError):
            make_client().passthrough.get("https://example.com/kling/v1/videos/text2video")


if __name__ == "__main__":
    unittest.main()
