from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from seaart_sdk import (
    ERR_NETWORK,
    ERR_TASK_FAILED,
    ERR_TIMEOUT,
    FaceScanRequest,
    AudioScanRequest,
    CharacterQualityScanRequest,
    ComfyUIInput,
    ImageScanRequest,
    ImageScanRiskTypeErotic,
    ImageScanRiskTypeViolent,
    ImageURL,
    ModelSearchParams,
    NewTask,
    SeaArtError,
    Text,
    TextContentScanRequest,
    VisualStructuredTextFusionScanRequest,
    TextScanAreaTypeForeign,
    TextScanRequest,
    TextScanWayDictionary,
    Task,
    Usage,
    WithHeader,
    WithPollInterval,
    WithPollTimeout,
)

from test_helpers import (
    FakeResponse,
    json_response,
    make_client,
    patch_urlopen,
    request_headers,
    request_json,
    request_path,
    sse_response,
)


class ModalServiceTests(unittest.TestCase):
    def test_usage_cost_float64_accepts_empty_string(self) -> None:
        self.assertEqual(Usage(cost="").cost_float64(), 0.0)
        self.assertEqual(Usage(cost="0.01429").cost_float64(), 0.01429)

    def test_create_submits_raw_body(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/generation")
            self.assertEqual(request_headers(request)["X-trace-id"], "trace-123")
            self.assertEqual(request_headers(request)["X-model"], "alibaba_wanx26_i2v_flash")
            body = request_json(request)
            self.assertTrue(body["moderation"])
            self.assertNotIn("model", body)
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

    def test_create_comfyui_task_builds_fixed_request_shape(self) -> None:
        raw_input = {"field": "select", "value": 1}

        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/generation")
            self.assertEqual(request_headers(request)["X-model"], "comfyui")
            body = request_json(request)
            self.assertNotIn("model", body)
            self.assertEqual(
                body,
                {
                    "input": [
                        {
                            "params": {
                                "template_id": "d32kq8le878c73876j5g",
                                "high_memory": True,
                                "inputs": [
                                    {
                                        "field": "image",
                                        "value": "https://example.com/input.webp",
                                        "node_id": "10",
                                    },
                                    {"field": "select", "value": 1},
                                ],
                            }
                        }
                    ]
                },
            )
            return json_response(200, {"id": "task_comfyui", "status": "in_progress", "model": "comfyui"})

        client = make_client()
        with patch_urlopen(handler):
            task = client.modal.create_comfyui_task(
                "d32kq8le878c73876j5g",
                [
                    ComfyUIInput(
                        field="image",
                        value="https://example.com/input.webp",
                        node_id="10",
                    ),
                    raw_input,
                ],
                high_memory=True,
            )

        self.assertEqual(task.id, "task_comfyui")
        self.assertEqual(raw_input, {"field": "select", "value": 1})

    def test_list_comfyui_templates_decodes_specs(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/template/specs")
            self.assertEqual(request_json(request), {"type": "comfyui", "template_ids": ["d595lcle878btf8lbq2g"]})
            return json_response(
                200,
                {
                    "type": "comfyui",
                    "templates": [
                        {
                            "template_id": "d595lcle878btf8lbq2g",
                            "template_name": "ReV Animated",
                            "description": "ComfyUI quick app",
                            "version": "d595lcle878btf8lbq30",
                            "inputs": [
                                {
                                    "field": "seed",
                                    "node_id": "3",
                                    "node_type": "KSampler",
                                    "type": "integer",
                                    "required": True,
                                    "description": "Seed",
                                    "parameter_type": 7,
                                    "parameter_value_type": 2,
                                    "constraints": {"max": 18446744073709552000, "default": 1070093600316061},
                                }
                            ],
                            "outputs": [{"node_id": "9", "node_type": "SaveImage"}],
                        }
                    ],
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.list_comfyui_templates(["d595lcle878btf8lbq2g"])

        self.assertEqual(response.type, "comfyui")
        self.assertEqual(response.templates[0].inputs[0].field, "seed")
        self.assertEqual(response.templates[0].inputs[0].constraints["max"], 18446744073709552000)
        self.assertEqual(response.templates[0].outputs[0].node_type, "SaveImage")

    def test_precharge_returns_billing_preview(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/generation/precharge")
            self.assertEqual(request_headers(request)["X-model"], "volces_seedream_4_5")
            body = request_json(request)
            self.assertEqual(body["id"], "d88pmute87128c73e9r0d0")
            self.assertNotIn("model", body)
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
            self.assertEqual(body["detected_age"], True)
            self.assertEqual(body["is_video"], False)
            self.assertEqual(body["callback_url"], "https://example.com/callback")
            self.assertEqual(body["callback_context"], {"trace_id": "trace-scan"})
            self.assertEqual(body["canary"], "B")
            self.assertEqual(body["scene"], "avatar")

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
                    detected_age=True,
                    is_video=False,
                    callback_url="https://example.com/callback",
                    callback_context={"trace_id": "trace-scan"},
                    canary="B",
                    scene="avatar",
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
            self.assertEqual(body["is_video"], False)
            return json_response(200, {"ok": True, "usage": {"cost": "0.001"}})

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_image(ImageScanRequest(img_base64="abc123"))

        self.assertTrue(response.ok)

    def test_scan_image_rejects_uri_and_img_base64_together(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.scan_image(ImageScanRequest(uri="https://example.com/image.jpg", img_base64="abc123"))

    def test_scan_image_rejects_video_with_img_base64(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.scan_image(ImageScanRequest(img_base64="abc123", is_video=True))

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
                    "req_id": "content-text-risk-1",
                    "level": 5,
                    "label": "pornography",
                    "reason": "Explicit sexual description",
                    "usage": {"cost": "0.001"},
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
        self.assertEqual(response.req_id, "content-text-risk-1")
        self.assertEqual(response.level, 5)
        self.assertEqual(response.label, "pornography")
        self.assertEqual(response.reason, "Explicit sexual description")
        self.assertIsNotNone(response.usage)
        self.assertEqual(response.usage.cost, "0.001")
        self.assertNotIn("req_id", response.extra)

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

    def test_scan_visual_structured_text_fusion_posts_request(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/visual/structured/text/fusion/scan")
            body = request_json(request)
            self.assertEqual(body["text_dict"]["name"], "小美")
            self.assertEqual(body["uri"], "https://example.com/cover.jpg")
            self.assertEqual(body["business_type"], "v1")
            self.assertEqual(body["detected_age"], 0)
            self.assertEqual(body["hash_comparison"], 1)
            self.assertEqual(body["canary"], "A")
            self.assertEqual(body["mode"], "mixed")
            self.assertEqual(body["ocr"], 1)
            return json_response(
                200,
                {
                    "ok": True,
                    "nsfw_level": 2,
                    "reason": "detected risk",
                    "img_reason": "adult content",
                    "text_reason": "inappropriate words",
                    "issue_source": "both",
                    "risk_keys": ["description", "greeting"],
                    "req_id": "fusion-1",
                    "usage": {"cost": "0.001"},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_visual_structured_text_fusion(
                VisualStructuredTextFusionScanRequest(
                    text_dict={"name": "小美", "greeting": "你好呀"},
                    uri="https://example.com/cover.jpg",
                    business_type="v1",
                    detected_age=0,
                    hash_comparison=1,
                    canary="A",
                    mode="mixed",
                    ocr=1,
                )
            )

        self.assertTrue(response.ok)
        self.assertEqual(response.nsfw_level, 2)
        self.assertEqual(response.issue_source, "both")
        self.assertEqual(response.risk_keys, ["description", "greeting"])
        self.assertEqual(response.req_id, "fusion-1")
        self.assertEqual(response.usage.cost, "0.001")
        self.assertNotIn("req_id", response.extra)

    def test_scan_visual_structured_text_fusion_requires_text_and_image(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.scan_visual_structured_text_fusion({"text_dict": {}})
        with self.assertRaises(SeaArtError):
            client.modal.scan_visual_structured_text_fusion({"uri": "https://example.com/cover.jpg"})

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

    def test_scan_audio_rejects_img_base64_raw_dict(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.scan_audio({"img_base64": "abc123", "rec_type": "custom"})

    def test_scan_character_quality_posts_flat_body(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/char/quality/scan")
            self.assertEqual(request_headers(request)["Authorization"], "Bearer test-key")
            self.assertEqual(
                request_json(request),
                {
                    "name": "Xiaomei",
                    "first_msg": "Hello.",
                    "description": "A thoughtful friend.",
                    "scenario": "A cafe on a rainy day.",
                    "example_dialogue": "A: Hello\\nB: Welcome.",
                },
            )
            return json_response(
                200,
                {
                    "ok": True,
                    "level": "A",
                    "safety_tag": {"tag": "normal"},
                    "usage": {"cost": "0.001"},
                    "request_id": "character-quality-1",
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            response = client.modal.scan_character_quality(
                CharacterQualityScanRequest(
                    name="Xiaomei",
                    first_msg="Hello.",
                    description="A thoughtful friend.",
                    scenario="A cafe on a rainy day.",
                    example_dialogue="A: Hello\\nB: Welcome.",
                ),
            )

        self.assertTrue(response.ok)
        self.assertEqual(response.level, "A")
        self.assertIsNotNone(response.safety_tag)
        self.assertEqual(response.safety_tag.tag, "normal")
        self.assertEqual(response.safety_tag.fields, {})
        self.assertIsNotNone(response.usage)
        self.assertEqual(response.usage.cost, "0.001")
        self.assertEqual(response.extra["request_id"], "character-quality-1")

    def test_scan_character_quality_rejects_non_string_fields(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.scan_character_quality({"name": "Xiaomei", "level": 1})

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

    def test_wait_failed_task_preserves_error_message_and_code(self) -> None:
        def handler(request):
            return json_response(
                200,
                {
                    "id": "task_fail_details",
                    "status": "failed",
                    "error": {"code": 110001, "message": "input image may contain sensitive information"},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            with self.assertRaises(SeaArtError) as context:
                client.modal.wait("task_fail_details", WithPollInterval(0.01), WithPollTimeout(1.0))

        self.assertEqual(context.exception.kind, ERR_TASK_FAILED)
        self.assertEqual(context.exception.code, 110001)
        self.assertEqual(context.exception.message, "task failed: input image may contain sensitive information")

    def test_wait_failed_task_accepts_empty_usage_cost(self) -> None:
        def handler(request):
            return json_response(
                200,
                {
                    "id": "task_fail_empty_cost",
                    "status": "failed",
                    "error": {"code": 190000, "message": "download input audio failed"},
                    "usage": {"cost": ""},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            with self.assertRaises(SeaArtError) as context:
                client.modal.wait("task_fail_empty_cost", WithPollInterval(0.01), WithPollTimeout(1.0))

        self.assertEqual(context.exception.kind, ERR_TASK_FAILED)
        self.assertEqual(context.exception.code, 190000)
        self.assertEqual(context.exception.message, "task failed: download input audio failed")

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


class ModalDeliveryTests(unittest.TestCase):
    """Synchronous and streamed generation delivery (gateway /v1/generation/sync)."""

    def test_create_sync_returns_the_final_result(self) -> None:
        """create_sync() 只让调用方说"给我结果"：路由与响应格式都由 SDK 决定。"""

        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/generation/sync")
            self.assertEqual(request_headers(request)["Accept"], "application/json")
            self.assertEqual(request_headers(request)["X-model"], "minimax_t2a")
            self.assertNotIn("model", request_json(request))
            return json_response(
                200,
                {
                    "id": "task_sync_1",
                    "status": "completed",
                    "model": "minimax_t2a",
                    "output": [{"content": [{"type": "audio", "url": "https://cdn.example.com/full.mp3"}]}],
                    "usage": {"cost": "0.0017", "discount": 1},
                    "metadata": {"completed_at": 1.2},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            task = client.modal.create_sync({"model": "minimax_t2a", "input": [{"params": {"text": "hi"}}]})

        self.assertEqual(task.id, "task_sync_1")
        self.assertEqual(task.status, "completed")
        self.assertEqual(task.urls(), ["https://cdn.example.com/full.mp3"])
        self.assertAlmostEqual(task.usage.cost_float64(), 0.0017)

    def test_create_sync_raises_when_the_task_failed(self) -> None:
        def handler(request):
            return json_response(
                200,
                {
                    "id": "task_sync_failed",
                    "status": "failed",
                    "model": "minimax_t2a",
                    "error": {"code": 110001, "message": "vendor rejected"},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            with self.assertRaises(SeaArtError) as context:
                client.modal.create_sync({"model": "minimax_t2a"})

        self.assertEqual(context.exception.kind, ERR_TASK_FAILED)
        self.assertEqual(context.exception.task_id, "task_sync_failed")
        self.assertIn("vendor rejected", context.exception.message)

    def test_create_sync_timeout_keeps_the_task_id(self) -> None:
        def handler(request):
            return json_response(
                504,
                {
                    "id": "task_sync_slow",
                    "status": "in_progress",
                    "error": {"code": "SYNC_TIMEOUT", "message": "waited 15m0s, still running"},
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            with self.assertRaises(SeaArtError) as context:
                client.modal.create_sync({"model": "slow_model"})

        self.assertEqual(context.exception.kind, ERR_TIMEOUT)
        self.assertEqual(context.exception.task_id, "task_sync_slow")
        self.assertEqual(context.exception.code, "SYNC_TIMEOUT")

    def test_create_stream_yields_chunks_then_done(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/v1/generation/sync")
            self.assertEqual(request_headers(request)["Accept"], "text/event-stream")
            return sse_response(
                'event: output\ndata: {"id":"task_stream","model":"minimax_t2a","status":"in_progress",'
                '"output":[{"content":[{"type":"audio","url":"https://cdn.example.com/0.wav","chunk_index":0}]}],"cursor":1}\n\n',
                ": keepalive\n\n",
                'event: output\ndata: {"id":"task_stream","model":"minimax_t2a","status":"in_progress",'
                '"output":[{"content":[{"type":"audio","url":"https://cdn.example.com/1.wav","chunk_index":1}]}],"cursor":2}\n\n',
                'event: done\ndata: {"id":"task_stream","status":"completed","model":"minimax_t2a",'
                '"output":[{"content":[{"type":"audio","url":"https://cdn.example.com/full.wav"}]}],'
                '"usage":{"cost":"0.0017","discount":1}}\n\n',
            )

        client = make_client()
        with patch_urlopen(handler):
            events = list(client.modal.create_stream({"model": "minimax_t2a"}))

        self.assertEqual([event.event for event in events], ["output", "output", "done"])
        self.assertEqual(events[0].task_id, "task_stream")
        self.assertEqual(events[0].cursor, 1)
        self.assertEqual(events[0].urls(), ["https://cdn.example.com/0.wav"])
        self.assertEqual(events[0].chunks[0].content[0].chunk_index, 0)
        # 分片帧的 status 恒为 in_progress：判断结束只能看 event
        self.assertEqual(events[0].raw["status"], "in_progress")
        self.assertFalse(events[0].done)
        self.assertTrue(events[-1].done)
        self.assertEqual(events[-1].task.status, "completed")
        self.assertEqual(events[-1].task.urls(), ["https://cdn.example.com/full.wav"])
        self.assertAlmostEqual(events[-1].task.usage.cost_float64(), 0.0017)

    def test_create_stream_error_event_is_terminal(self) -> None:
        def handler(request):
            return sse_response(
                'event: error\ndata: {"id":"task_stream","model":"minimax_t2a","status":"in_progress",'
                '"error":{"code":"SYNC_TIMEOUT","message":"waited too long"}}\n\n',
            )

        client = make_client()
        with patch_urlopen(handler):
            events = list(client.modal.create_stream({"model": "minimax_t2a"}))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, "error")
        self.assertEqual(events[0].error_code, "SYNC_TIMEOUT")
        self.assertEqual(events[0].error_message, "waited too long")
        self.assertTrue(events[0].done)

    def test_create_stream_raises_on_http_error_before_streaming(self) -> None:
        def handler(request):
            return json_response(429, {"error": {"code": 1002, "message": "rate limited"}})

        client = make_client()
        with patch_urlopen(handler):
            with self.assertRaises(SeaArtError) as context:
                list(client.modal.create_stream({"model": "minimax_t2a"}))

        self.assertEqual(context.exception.kind, "quota")
        self.assertEqual(context.exception.status, 429)

    def test_subscribe_resumes_from_cursor(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request_path(request), "/v1/generation/task/task_resume/stream")
            self.assertEqual(parse_qs(urlparse(request.full_url).query), {"cursor": ["3"]})
            self.assertEqual(request_headers(request)["Accept"], "text/event-stream")
            return sse_response(
                'event: output\ndata: {"id":"task_resume","status":"in_progress","output":[{"content":[{"type":"audio","url":"https://cdn.example.com/3.wav","chunk_index":3}]}],"cursor":4}\n\n',
                'event: done\ndata: {"id":"task_resume","status":"completed","output":[{"content":[{"type":"audio","url":"https://cdn.example.com/full.wav"}]}],"usage":{"cost":"0.003"}}\n\n',
            )

        client = make_client()
        with patch_urlopen(handler):
            events = list(client.modal.subscribe("task_resume", cursor=3))

        self.assertEqual(events[0].cursor, 4)
        self.assertEqual(events[0].urls(), ["https://cdn.example.com/3.wav"])
        self.assertEqual(events[-1].task.id, "task_resume")

    def test_task_stream_uses_subscribe(self) -> None:
        task = Task(id="task_bound", status="in_progress")

        def handler(request):
            self.assertEqual(request_path(request), "/v1/generation/task/task_bound/stream")
            return sse_response(
                'event: done\ndata: {"id":"task_bound","status":"completed","output":[]}\n\n',
            )

        client = make_client()
        task._service = client.modal
        with patch_urlopen(handler):
            events = list(task.stream())

        self.assertTrue(events[-1].done)
        self.assertEqual(events[-1].task.id, "task_bound")

    def test_create_sync_accepts_the_typed_builder_body(self) -> None:
        """NewTask(...).build() 与手写 dict 等价，新方法两者都吃。"""

        def handler(request):
            self.assertEqual(request_path(request), "/v1/generation/sync")
            self.assertEqual(request_headers(request)["Accept"], "application/json")
            self.assertEqual(request_headers(request)["X-model"], "alibaba_wanx26_i2v_flash")
            body = request_json(request)
            self.assertNotIn("model", body)
            self.assertTrue(body["moderation"])
            self.assertEqual(body["metadata"], {"trace_id": "trace-123"})
            self.assertEqual(body["input"][0]["params"]["parameters"]["duration"], 5)
            return json_response(
                200,
                {
                    "id": "task_builder",
                    "status": "completed",
                    "model": "alibaba_wanx26_i2v_flash",
                    "output": [{"content": [{"type": "url", "url": "https://cdn.example.com/out.mp4"}]}],
                    "usage": {"cost": "0.2"},
                },
            )

        built = (
            NewTask("alibaba_wanx26_i2v_flash")
            .moderation(True)
            .params(
                {
                    "input": {"img_url": "https://x/y.jpg", "prompt": "a dog"},
                    "parameters": {"resolution": "720P", "duration": 5},
                }
            )
            .metadata("trace_id", "trace-123")
            .build()
        )

        client = make_client()
        with patch_urlopen(handler):
            task = client.modal.create_sync(built)

        self.assertEqual(task.status, "completed")
        self.assertEqual(task.urls(), ["https://cdn.example.com/out.mp4"])

    def test_create_stream_accepts_the_typed_builder_body(self) -> None:
        def handler(request):
            self.assertEqual(request_headers(request)["X-model"], "alibaba_wanx26_i2v_flash")
            self.assertNotIn("model", request_json(request))
            return sse_response(
                'event: output\ndata: {"id":"task_builder_s","status":"in_progress",'
                '"output":[{"content":[{"type":"url","url":"https://cdn.example.com/0.mp4"}]}],"cursor":1}\n\n',
                'event: done\ndata: {"id":"task_builder_s","status":"completed","output":[]}\n\n',
            )

        built = NewTask("alibaba_wanx26_i2v_flash").params({"input": {"prompt": "a dog"}}).build()

        client = make_client()
        with patch_urlopen(handler):
            events = list(client.modal.create_stream(built))

        self.assertEqual(events[0].urls(), ["https://cdn.example.com/0.mp4"])
        self.assertEqual(events[-1].task.id, "task_builder_s")

    def test_create_stream_fails_when_the_stream_ends_without_a_terminal_event(self) -> None:
        """提前断流不能被当成成功；已到达的分片仍要交付。"""

        def handler(request):
            return sse_response(
                'event: output\ndata: {"id":"task_trunc","status":"in_progress",'
                '"output":[{"content":[{"type":"audio","url":"https://cdn.example.com/0.wav"}]}],"cursor":1}\n\n',
            )

        client = make_client()
        received = []
        with patch_urlopen(handler):
            with self.assertRaises(SeaArtError) as ctx:
                for event in client.modal.create_stream({"model": "m"}):
                    received.append(event)

        self.assertEqual(ctx.exception.kind, ERR_NETWORK)
        self.assertIn("terminal event", str(ctx.exception))
        self.assertEqual(len(received), 1, "分片已经交付，不能因为报错丢掉")
        self.assertEqual(received[0].urls(), ["https://cdn.example.com/0.wav"])

    def test_create_stream_exposes_the_frame_status(self) -> None:
        def handler(request):
            return sse_response(
                'event: output\ndata: {"id":"task_s","status":"in_progress",'
                '"output":[{"content":[{"type":"audio","url":"https://cdn.example.com/0.wav"}]}],"cursor":1}\n\n',
                'event: done\ndata: {"id":"task_s","status":"completed","output":[]}\n\n',
            )

        client = make_client()
        with patch_urlopen(handler):
            events = list(client.modal.create_stream({"model": "m"}))

        self.assertEqual(events[0].status, "in_progress")
        self.assertEqual(events[1].status, "completed")
        self.assertFalse(events[0].done)
        self.assertTrue(events[1].done)

    def test_create_stream_reads_error_message_from_the_gateway(self) -> None:
        def handler(request):
            return sse_response(
                'event: error\ndata: {"id":"task_s","status":"in_progress",'
                '"error":{"code":"SYNC_TIMEOUT","error_message":"still running"}}\n\n',
            )

        client = make_client()
        with patch_urlopen(handler):
            events = list(client.modal.create_stream({"model": "m"}))

        self.assertEqual(events[0].error_code, "SYNC_TIMEOUT")
        self.assertEqual(events[0].error_message, "still running")
        self.assertTrue(events[0].done)

    def test_create_stream_surfaces_malformed_frames(self) -> None:
        def handler(request):
            return sse_response(
                "event: output\ndata: {not json\n\n",
                'event: done\ndata: {"id":"task_bad","status":"completed","output":[]}\n\n',
            )

        client = make_client()
        with patch_urlopen(handler):
            events = list(client.modal.create_stream({"model": "m"}))

        self.assertIsNotNone(events[0].err, "畸形帧必须暴露失败原因")
        self.assertIn("decode stream frame", str(events[0].err))
        self.assertTrue(events[1].done, "单帧损坏不终止整条流")
        self.assertEqual(events[1].task.status, "completed")

    def test_subscribe_requires_task_id(self) -> None:
        client = make_client()
        with self.assertRaises(SeaArtError):
            client.modal.subscribe("  ")


if __name__ == "__main__":
    unittest.main()
