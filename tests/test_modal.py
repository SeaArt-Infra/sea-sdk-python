from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from seaart_sdk import (
    ERR_TASK_FAILED,
    ImageURL,
    ModelSearchParams,
    NewTask,
    SeaArtError,
    Text,
    WithHeader,
    WithPollInterval,
    WithPollTimeout,
)

from test_helpers import FakeResponse, json_response, make_client, patch_urlopen, request_headers, request_json, request_path


class ModalServiceTests(unittest.TestCase):
    def test_create_submits_raw_body(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/generation")
            self.assertEqual(request_headers(request)["X-trace-id"], "trace-123")
            body = request_json(request)
            self.assertEqual(body["model"], "vidu_q3_reference")
            self.assertEqual(body["parameters"]["duration"], 5)
            return json_response(
                200,
                {"id": "task_create", "status": "in_progress", "model": "vidu_q3_reference"},
            )

        client = make_client()
        with patch_urlopen(handler):
            task = client.modal.create(
                {
                    "model": "vidu_q3_reference",
                    "input": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "cinematic shot"},
                                {"type": "image_url", "url": "https://example.com/ref1.webp"},
                            ],
                        }
                    ],
                    "parameters": {"duration": 5},
                },
                WithHeader("X-Trace-Id", "trace-123"),
            )
        self.assertEqual(task.id, "task_create")
        self.assertEqual(task.status, "in_progress")
        self.assertEqual(task.model, "vidu_q3_reference")

    def test_get_returns_task(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request_path(request), "/v1/generation/task/task_abc123")
            return json_response(
                200,
                {
                    "id": "task_abc123",
                    "status": "completed",
                    "progress": 1.0,
                    "model": "vidu_q3_reference",
                    "output": [
                        {"content": [{"type": "video", "url": "https://example.com/out.mp4"}]}
                    ],
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            task = client.modal.get("task_abc123")
        self.assertEqual(task.id, "task_abc123")
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.progress, 1.0)
        self.assertEqual(task.urls(), ["https://example.com/out.mp4"])

    def test_list_models_searches_skill_models(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request_path(request), "/v1/models/skill/search")
            self.assertEqual(request_headers(request)["Authorization"], "Bearer test-key")
            self.assertEqual(request_headers(request)["Accept"], "application/json")

            query = parse_qs(urlparse(request.full_url).query)
            self.assertEqual(query["q"], ["animate"])
            self.assertEqual(query["input"], ["image"])
            self.assertEqual(query["output"], ["video"])
            self.assertEqual(query["type"], ["i2v"])
            self.assertEqual(query["provider"], ["alibaba"])
            self.assertEqual(query["limit"], ["2"])

            return json_response(
                200,
                {
                    "hits": [
                        {
                            "id": "alibaba_animate_anyone_detect",
                            "name": "alibaba_animate_anyone_detect",
                            "provider": "alibaba",
                            "input": "image",
                            "output": "video",
                            "media_type": "video",
                            "tags": ["i2v"],
                            "tags_abbr": "i2v",
                            "skill_content": "# alibaba_animate_anyone_detect",
                        }
                    ],
                    "query": "animate",
                    "limit": 2,
                    "estimatedTotalHits": 1,
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.list_models(
                ModelSearchParams(
                    query="animate",
                    input="image",
                    output="video",
                    type="i2v",
                    provider="alibaba",
                    limit=2,
                )
            )

        self.assertEqual(response.query, "animate")
        self.assertEqual(response.limit, 2)
        self.assertEqual(response.estimated_total_hits, 1)
        self.assertEqual(len(response.hits), 1)
        self.assertEqual(response.hits[0]["name"], "alibaba_animate_anyone_detect")

    def test_search_models_alias(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request_path(request), "/v1/models/skill/search")
            query = parse_qs(urlparse(request.full_url).query, keep_blank_values=True)
            self.assertEqual(query["q"], [""])
            self.assertEqual(query["limit"], ["2"])
            return json_response(200, {"hits": [], "query": "", "limit": 2})

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.search_models(ModelSearchParams(limit=2))

        self.assertEqual(response.limit, 2)

    def test_get_model_skill_returns_markdown(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request_path(request), "/v1/models/skill/alibaba_animate_anyone_detect")
            self.assertEqual(request_headers(request)["Authorization"], "Bearer test-key")
            self.assertEqual(request_headers(request)["Accept"], "application/json")
            return FakeResponse(
                200,
                b"# alibaba_animate_anyone_detect\n\nparameters",
                headers={"Content-Type": "text/markdown; charset=utf-8"},
            )

        client = make_client()
        with patch_urlopen(handler):
            content = client.modal.get_model_skill("alibaba_animate_anyone_detect")

        self.assertEqual(content, "# alibaba_animate_anyone_detect\n\nparameters")

    def test_get_model_skill_requires_model(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.get_model_skill(" ")

    def test_wait_completes(self) -> None:
        polls = {"count": 0}

        def handler(request):
            polls["count"] += 1
            if polls["count"] == 1:
                return json_response(
                    200,
                    {
                        "id": "task_wait",
                        "status": "in_progress",
                        "progress": 0.4,
                        "model": "vidu_q3_reference",
                    },
                )
            return json_response(
                200,
                {
                    "id": "task_wait",
                    "status": "completed",
                    "progress": 1.0,
                    "model": "vidu_q3_reference",
                    "output": [
                        {"content": [{"type": "video", "url": "https://example.com/out.mp4"}]}
                    ],
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            task = client.modal.wait(
                "task_wait",
                WithPollInterval(0.01),
                WithPollTimeout(1.0),
            )
        self.assertEqual(task.status, "completed")
        self.assertEqual(polls["count"], 2)

    def test_task_wait_uses_attached_client(self) -> None:
        polls = {"count": 0}

        def handler(request):
            path = request_path(request)
            if path == "/v1/generation":
                return json_response(
                    200,
                    {"id": "task_attached", "status": "in_progress", "model": "vidu_q3_reference"},
                )
            if path == "/v1/generation/task/task_attached":
                polls["count"] += 1
                return json_response(
                    200,
                    {
                        "id": "task_attached",
                        "status": "completed",
                        "progress": 1.0,
                        "model": "vidu_q3_reference",
                    },
                )
            self.fail(f"unexpected path {path}")

        client = make_client()
        with patch_urlopen(handler):
            task = client.modal.create({"model": "vidu_q3_reference"})
            task = task.wait(WithPollInterval(0.01), WithPollTimeout(1.0))

        self.assertEqual(task.status, "completed")
        self.assertEqual(polls["count"], 1)

    def test_wait_failed_task(self) -> None:
        def handler(request):
            return json_response(
                200,
                {
                    "id": "task_fail",
                    "status": "failed",
                    "error": {"error_message": "provider rejected request"},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            with self.assertRaises(SeaArtError) as context:
                client.modal.wait(
                    "task_fail",
                    WithPollInterval(0.01),
                    WithPollTimeout(1.0),
                )
        self.assertEqual(context.exception.kind, ERR_TASK_FAILED)

    def test_task_builder_builds_generic_request(self) -> None:
        body = (
            NewTask("vidu_q3_reference")
            .user(
                Text("cinematic shot"),
                ImageURL("https://example.com/ref1.webp"),
            )
            .param("duration", 5)
            .metadata_item("trace_id", "trace-123")
            .build()
        )
        self.assertEqual(body["model"], "vidu_q3_reference")
        self.assertEqual(body["metadata"]["trace_id"], "trace-123")


if __name__ == "__main__":
    unittest.main()
