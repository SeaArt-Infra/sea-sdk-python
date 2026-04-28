from __future__ import annotations

import unittest

from seaart_sdk import ERR_TASK_FAILED, ImageURL, NewTask, SeaArtError, Text, WithHeader, WithPollInterval, WithPollTimeout

from test_helpers import json_response, make_client, patch_urlopen, request_headers, request_json, request_path


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
