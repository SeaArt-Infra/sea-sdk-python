from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from seaart_sdk import (
    ERR_TASK_FAILED,
    FaceScanRequest,
    ImageScanRequest,
    ImageScanRiskTypeErotic,
    ImageScanRiskTypeViolent,
    ImageURL,
    ModelSearchParams,
    NewTask,
    SeaArtError,
    Text,
    TextScanRequest,
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

    def test_scan_image_posts_image_scan_request(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/image/scan")
            self.assertEqual(request_headers(request)["Authorization"], "Bearer test-key")
            self.assertEqual(request_headers(request)["X-trace-id"], "trace-scan")

            body = request_json(request)
            self.assertEqual(body["uri"], "https://example.com/image.jpg")
            self.assertEqual(body["risk_types"], ["EROTIC", "VIOLENT"])
            self.assertEqual(body["detected_age"], 1)
            self.assertEqual(body["is_video"], 0)

            return json_response(
                200,
                {
                    "ok": True,
                    "nsfw_level": 2,
                    "label_items": [{"name": "safe", "score": 2, "risk_type": "EROTIC"}],
                    "risk_types": ["EROTIC"],
                    "usage": {"cost": "0.001"},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_image(
                ImageScanRequest(
                    uri="https://example.com/image.jpg",
                    risk_types=[ImageScanRiskTypeErotic, ImageScanRiskTypeViolent],
                    detected_age=1,
                ),
                WithHeader("X-Trace-Id", "trace-scan"),
            )

        self.assertTrue(response.ok)
        self.assertEqual(response.nsfw_level, 2)
        self.assertEqual(response.label_items[0].risk_type, "EROTIC")
        self.assertIsNotNone(response.usage)
        self.assertEqual(response.usage.cost, "0.001")

    def test_scan_image_accepts_raw_dict(self) -> None:
        def handler(request):
            self.assertEqual(request_path(request), "/v1/image/scan")
            self.assertEqual(request_json(request)["is_video"], 1)
            return json_response(
                200,
                {
                    "ok": True,
                    "frame_results": [
                        {
                            "frame_index": 3,
                            "nsfw_level": 1,
                            "risk_types": ["VIOLENT"],
                        }
                    ],
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_image(
                {
                    "uri": "https://example.com/video.mp4",
                    "risk_types": [ImageScanRiskTypeViolent],
                    "is_video": 1,
                    "duration": 5.2,
                }
            )

        self.assertEqual(response.frame_results[0].frame_index, 3)
        self.assertEqual(response.frame_results[0].risk_types, ["VIOLENT"])

    def test_scan_image_requires_uri(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.scan_image(ImageScanRequest(uri=" "))

    def test_scan_face_posts_face_scan_request(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/face/scan")
            self.assertEqual(request_headers(request)["Authorization"], "Bearer test-key")
            self.assertEqual(request_headers(request)["X-trace-id"], "trace-face")

            body = request_json(request)
            self.assertEqual(body["uri"], "https://example.com/face.jpg")
            self.assertEqual(body["is_video"], 0)
            self.assertEqual(body["canary"], "gray")
            self.assertEqual(body["scene"], "avatar")

            return json_response(
                200,
                {
                    "ok": True,
                    "face_count": 1,
                    "faces": [{"score": 0.99}],
                    "usage": {"cost": "0.002"},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_face(
                FaceScanRequest(
                    uri="https://example.com/face.jpg",
                    is_video=0,
                    canary="gray",
                    scene="avatar",
                ),
                WithHeader("X-Trace-Id", "trace-face"),
            )

        self.assertTrue(response.ok)
        self.assertIsNotNone(response.usage)
        self.assertEqual(response.usage.cost, "0.002")
        self.assertEqual(response.extra["face_count"], 1)
        self.assertEqual(response.extra["faces"][0]["score"], 0.99)

    def test_scan_face_accepts_raw_dict_and_base64(self) -> None:
        def handler(request):
            self.assertEqual(request_path(request), "/v1/face/scan")
            body = request_json(request)
            self.assertEqual(body["img_base64"], "abc123")
            self.assertEqual(body["is_video"], 1)
            self.assertEqual(body["duration"], 12.5)
            return json_response(200, {"ok": True, "video_duration": 12.5})

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_face(
                {
                    "img_base64": "abc123",
                    "is_video": 1,
                    "duration": 12.5,
                }
            )

        self.assertEqual(response.extra["video_duration"], 12.5)

    def test_scan_face_requires_uri_or_base64(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.scan_face(FaceScanRequest(uri=" ", img_base64=" "))

    def test_scan_text_posts_text_scan_request(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/text/scan")
            self.assertEqual(request_headers(request)["Authorization"], "Bearer test-key")
            self.assertEqual(request_headers(request)["X-trace-id"], "trace-text")

            body = request_json(request)
            self.assertEqual(body["text"], "a prompt to check")
            self.assertEqual(body["scene"], 1)
            self.assertEqual(body["area_types"], [1, 2])
            self.assertEqual(body["way"], 2)
            self.assertEqual(body["scenes"], ["prompt"])

            return json_response(
                200,
                {
                    "code": 0,
                    "message": "ok",
                    "result": {"pass": True},
                    "usage": {"cost": "0.003"},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_text(
                TextScanRequest(
                    text="a prompt to check",
                    scene=1,
                    area_types=[1, 2],
                    way=2,
                    scenes=["prompt"],
                ),
                WithHeader("X-Trace-Id", "trace-text"),
            )

        self.assertIsNotNone(response.usage)
        self.assertEqual(response.usage.cost, "0.003")
        self.assertEqual(response.extra["code"], 0)
        self.assertEqual(response.extra["result"]["pass"], True)

    def test_scan_text_accepts_raw_dict(self) -> None:
        def handler(request):
            self.assertEqual(request_path(request), "/v1/text/scan")
            self.assertEqual(request_json(request)["scene"], 2)
            return json_response(200, {"code": 0, "result": {"pass": False}})

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_text({"text": "raw prompt", "scene": 2})

        self.assertEqual(response.extra["result"]["pass"], False)

    def test_scan_text_requires_text(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.scan_text(TextScanRequest(text=" "))

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
