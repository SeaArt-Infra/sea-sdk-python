from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from seaart_sdk import (
    ERR_TASK_FAILED,
    FaceScanRequest,
    AudioScanRequest,
    ImageScanRequest,
    ImageScanRiskTypeErotic,
    ImageScanRiskTypeViolent,
    ImageURL,
    ModelSearchParams,
    NewTask,
    SeaArtError,
    Text,
    TextContentScanRequest,
    TextScanAreaTypeForeign,
    TextScanRequest,
    TextScanWayDictionary,
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
            self.assertTrue(body["moderation"])
            self.assertEqual(body["model"], "alibaba_wanx26_i2v_flash")
            self.assertEqual(
                body["input"][0]["params"]["input"]["img_url"],
                "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg",
            )
            self.assertEqual(body["input"][0]["params"]["parameters"]["duration"], 5)
            return json_response(
                200,
                {"id": "task_create", "status": "in_progress", "model": "alibaba_wanx26_i2v_flash"},
            )

        client = make_client()
        with patch_urlopen(handler):
            task = client.modal.create(
                {
                    "moderation": True,
                    "model": "alibaba_wanx26_i2v_flash",
                    "input": [
                        {
                            "params": {
                                "input": {
                                    "img_url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg",
                                    "prompt": "小狗和女孩在秋天的公园里快乐地玩耍",
                                },
                                "parameters": {
                                    "resolution": "720P",
                                    "duration": 5,
                                    "prompt_extend": True,
                                    "watermark": False,
                                },
                            },
                        }
                    ],
                },
                WithHeader("X-Trace-Id", "trace-123"),
            )
        self.assertEqual(task.id, "task_create")
        self.assertEqual(task.status, "in_progress")
        self.assertEqual(task.model, "alibaba_wanx26_i2v_flash")

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

    def test_precharge_returns_billing_preview(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/generation/precharge")
            body = request_json(request)
            self.assertEqual(body["id"], "d88pmute87128c73e9r0d0")
            self.assertEqual(body["model"], "volces_seedream_4_5")
            self.assertFalse(body["moderation"])
            self.assertEqual(body["input"][0]["params"]["prompt"], "A dog")
            return json_response(
                200,
                {
                    "data": {
                        "billing_model": "volces_seedream_4_5",
                        "cost": "0.035714285714",
                        "currency": "USD",
                        "discount": 0.7,
                        "hash": "v1:18a733f04d227d572950ed8f1f98a9ba4cd37c168c5c98c05a5e574984f58eaf",
                        "model": "volces_seedream_4_5",
                        "original_model": "volces_seedream_4_5",
                        "sample_count": 4,
                        "updated_at": 1780633394064,
                    },
                    "status": "success",
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.precharge(
                {
                    "id": "d88pmute87128c73e9r0d0",
                    "model": "volces_seedream_4_5",
                    "input": [
                        {
                            "params": {
                                "prompt": "A dog",
                            }
                        }
                    ],
                    "moderation": False,
                }
            )

        self.assertEqual(response.status, "success")
        self.assertIsNotNone(response.data)
        self.assertEqual(response.data.billing_model, "volces_seedream_4_5")
        self.assertEqual(response.data.cost, "0.035714285714")
        self.assertEqual(response.data.currency, "USD")
        self.assertEqual(response.data.sample_count, 4)

    def test_precharge_supports_cache_miss_response(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/generation/precharge")
            return json_response(
                200,
                {
                    "data": {
                        "cost": None,
                        "hash": "v1:02833b68895eeb61bf214d35fd669502ef788e4c8d58505893414ae9632ca8ab",
                        "model": "volces_seedream_4_5",
                        "original_model": "volces_seedream_4_5",
                        "reason": "COST_CACHE_MISS",
                    },
                    "status": "failed",
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.precharge(
                {
                    "id": "d88pmute87128c73e9r0d0",
                    "model": "volces_seedream_4_5",
                    "input": [{"params": {"prompt": "A dog"}}],
                    "moderation": False,
                }
            )

        self.assertEqual(response.status, "failed")
        self.assertIsNotNone(response.data)
        self.assertIsNone(response.data.cost)
        self.assertEqual(response.data.reason, "COST_CACHE_MISS")

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

    def test_scan_image_accepts_img_base64(self) -> None:
        def handler(request):
            self.assertEqual(request_path(request), "/v1/image/scan")
            body = request_json(request)
            self.assertNotIn("uri", body)
            self.assertEqual(body["img_base64"], "abc123")
            return json_response(200, {"ok": True, "usage": {"cost": "0.001"}})

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_image(ImageScanRequest(img_base64="abc123"))

        self.assertTrue(response.ok)

    def test_scan_image_requires_uri_or_img_base64(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.scan_image(ImageScanRequest(uri=" ", img_base64=" "))

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
            self.assertEqual(body["area_types"], [2])
            self.assertEqual(body["way"], 0)

            return json_response(
                200,
                {
                    "data": {
                        "sensitive_words": [
                            {
                                "word": "blocked",
                                "start_index": 2,
                                "end_index": 8,
                                "risk_type_code": "political",
                            }
                        ],
                        "combination": {"rule": "pair"},
                        "is_sensitive": True,
                    },
                    "status": {
                        "code": 10000,
                        "msg": "success",
                        "request_id": "risk-req-1",
                    },
                    "usage": {"cost": "0.003"},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_text(
                TextScanRequest(
                    text="a prompt to check",
                    scene=1,
                    area_types=[TextScanAreaTypeForeign],
                    way=TextScanWayDictionary,
                ),
                WithHeader("X-Trace-Id", "trace-text"),
            )

        self.assertIsNotNone(response.status)
        self.assertEqual(response.status.code, 10000)
        self.assertEqual(response.status.request_id, "risk-req-1")
        self.assertIsNotNone(response.data)
        self.assertEqual(len(response.data.sensitive_words), 1)
        word = response.data.sensitive_words[0]
        self.assertEqual(word.word, "blocked")
        self.assertEqual(word.start_index, 2)
        self.assertEqual(word.end_index, 8)
        self.assertEqual(word.risk_type_code, "political")
        self.assertEqual(response.data.combination, {"rule": "pair"})
        self.assertTrue(response.data.is_sensitive)
        self.assertIsNotNone(response.usage)
        self.assertEqual(response.usage.cost, "0.003")
        self.assertEqual(response.extra, {})

    def test_scan_text_preserves_empty_result_fields(self) -> None:
        def handler(request):
            self.assertEqual(request_path(request), "/v1/text/scan")
            return json_response(
                200,
                {
                    "data": {
                        "sensitive_words": [],
                        "combination": None,
                        "is_sensitive": False,
                    },
                    "status": {
                        "code": 10000,
                        "msg": "success",
                        "request_id": "risk-empty",
                    },
                    "usage": {"cost": "1"},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_text(
                TextScanRequest(
                    text="clean prompt",
                    scene=1,
                    area_types=[TextScanAreaTypeForeign],
                    way=TextScanWayDictionary,
                )
            )

        self.assertIsNotNone(response.data)
        self.assertEqual(response.data.sensitive_words, [])
        self.assertIsNone(response.data.combination)
        self.assertFalse(response.data.is_sensitive)

    def test_scan_text_accepts_raw_dict(self) -> None:
        def handler(request):
            self.assertEqual(request_path(request), "/v1/text/scan")
            self.assertEqual(request_json(request)["scene"], 2)
            return json_response(
                200,
                {
                    "data": {"sensitive_words": []},
                    "status": {"code": 10000, "msg": "success"},
                    "debug": {"pass": False},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_text({"text": "raw prompt", "scene": 2})

        self.assertEqual(response.status.code, 10000)
        self.assertEqual(response.extra["debug"]["pass"], False)

    def test_scan_text_requires_text(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.scan_text(TextScanRequest(text=" "))

    def test_scan_text_content_posts_content_scan_request(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/text/content/scan")
            self.assertEqual(request_headers(request)["Authorization"], "Bearer test-key")
            self.assertEqual(request_headers(request)["X-trace-id"], "trace-content-text")

            body = request_json(request)
            self.assertEqual(body["text"], "hello world")
            self.assertEqual(body["canary"], "A")
            self.assertEqual(body["scene"], "user_name")

            return json_response(
                200,
                {
                    "ok": True,
                    "level": 5,
                    "label": "pornography",
                    "reason": "Explicit sexual description",
                    "usage": {"cost": "0.001"},
                    "request_id": "content-text-risk-1",
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_text_content(
                TextContentScanRequest(
                    text="hello world",
                    canary="A",
                    scene="user_name",
                ),
                WithHeader("X-Trace-Id", "trace-content-text"),
            )

        self.assertTrue(response.ok)
        self.assertEqual(response.level, 5)
        self.assertEqual(response.label, "pornography")
        self.assertEqual(response.reason, "Explicit sexual description")
        self.assertIsNotNone(response.usage)
        self.assertEqual(response.usage.cost, "0.001")
        self.assertEqual(response.extra["request_id"], "content-text-risk-1")

    def test_scan_text_content_accepts_raw_dict(self) -> None:
        def handler(request):
            self.assertEqual(request_path(request), "/v1/text/content/scan")
            self.assertEqual(request_json(request)["scene"], "seasoul")
            return json_response(
                200,
                {
                    "ok": True,
                    "level": 0,
                    "label": "normal",
                    "reason": "Neutral greeting expression",
                    "usage": {"cost": "0.001"},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_text_content(
                {
                    "text": "raw prompt",
                    "scene": "seasoul",
                }
            )

        self.assertTrue(response.ok)
        self.assertEqual(response.level, 0)
        self.assertEqual(response.label, "normal")

    def test_scan_text_content_requires_text(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.scan_text_content(TextContentScanRequest(text=" "))

    def test_scan_audio_posts_audio_scan_request(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/audio/scan")
            self.assertEqual(request_headers(request)["Authorization"], "Bearer test-key")
            self.assertEqual(request_headers(request)["X-trace-id"], "trace-audio")

            body = request_json(request)
            self.assertEqual(body["uri"], "https://example.com/audio/test.mp3")
            self.assertEqual(body["rec_type"], "AUDIOPOLITICAL_MOAN_ANTHEN")
            self.assertEqual(body["duration"], 15.0)

            return json_response(
                200,
                {
                    "riskDescription": "涉政音频",
                    "riskLevel": "REJECT",
                    "allLabels": [
                        {
                            "label1": "politics",
                            "label2": "leader",
                            "description": "涉政内容",
                        }
                    ],
                    "usage": {"cost": "0.001"},
                    "request_id": "audio-risk-1",
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_audio(
                AudioScanRequest(
                    uri="https://example.com/audio/test.mp3",
                    rec_type="AUDIOPOLITICAL_MOAN_ANTHEN",
                    duration=15.0,
                ),
                WithHeader("X-Trace-Id", "trace-audio"),
            )

        self.assertEqual(response.risk_description, "涉政音频")
        self.assertEqual(response.risk_level, "REJECT")
        self.assertEqual(response.all_labels[0].label1, "politics")
        self.assertIsNotNone(response.usage)
        self.assertEqual(response.usage.cost, "0.001")
        self.assertEqual(response.extra["request_id"], "audio-risk-1")

    def test_scan_audio_accepts_raw_dict(self) -> None:
        def handler(request):
            self.assertEqual(request_path(request), "/v1/audio/scan")
            self.assertEqual(request_json(request)["rec_type"], "custom")
            return json_response(200, {"riskDescription": "正常", "riskLevel": "PASS", "allLabels": []})

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_audio(
                {
                    "uri": "https://example.com/audio/clean.mp3",
                    "rec_type": "custom",
                }
            )

        self.assertEqual(response.risk_level, "PASS")
        self.assertEqual(response.all_labels, [])

    def test_scan_audio_requires_uri(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.scan_audio(AudioScanRequest(uri=" "))

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
            NewTask("alibaba_wanx26_i2v_flash")
            .moderation(True)
            .params(
                {
                    "input": {
                        "img_url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg",
                        "prompt": "小狗和女孩在秋天的公园里快乐地玩耍",
                    },
                    "parameters": {
                        "resolution": "720P",
                        "duration": 5,
                        "prompt_extend": True,
                        "watermark": False,
                    },
                }
            )
            .metadata_item("trace_id", "trace-123")
            .build()
        )
        self.assertTrue(body["moderation"])
        self.assertEqual(body["model"], "alibaba_wanx26_i2v_flash")
        self.assertEqual(
            body["input"][0]["params"]["input"]["img_url"],
            "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg",
        )
        self.assertEqual(body["input"][0]["params"]["parameters"]["resolution"], "720P")
        self.assertEqual(body["input"][0]["params"]["parameters"]["duration"], 5)
        self.assertEqual(body["metadata"]["trace_id"], "trace-123")

    def test_task_builder_supports_flat_params_and_top_level_fields(self) -> None:
        body = (
            NewTask("grok_imagine_image")
            .field("dash_scope", True)
            .moderation(True)
            .params(
                {
                    "aspect_ratio": "1:2",
                    "prompt": "Lego art version of Superman and Batman，Night scene",
                    "n": 1,
                    "resolution": "1k",
                }
            )
            .build()
        )

        self.assertTrue(body["dash_scope"])
        self.assertTrue(body["moderation"])
        self.assertEqual(body["model"], "grok_imagine_image")
        self.assertEqual(body["input"][0]["params"]["aspect_ratio"], "1:2")
        self.assertEqual(
            body["input"][0]["params"]["prompt"],
            "Lego art version of Superman and Batman，Night scene",
        )
        self.assertEqual(body["input"][0]["params"]["n"], 1)
        self.assertEqual(body["input"][0]["params"]["resolution"], "1k")

if __name__ == "__main__":
    unittest.main()
