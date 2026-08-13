# Sea Python SDK

Sea AI Platform Python SDK for calling multimodal, LLM, and vendor passthrough capabilities through the unified gateway.

Features:

- Standard-library implementation with no third-party runtime dependencies
- Preserves raw request passthrough capabilities
- Supports SSE streaming response parsing
- Supports task polling and a general task builder

## Feature Navigation

| Service | Client Field | Capability |
|------|-------------|------|
| [Multimodal API](#multimodal-api) | `client.modal` / `client.Modal` | Model listing, parameter details, generation tasks, precharge estimates, and vendor passthrough |
| [ComfyUI Quick Apps](#comfyui-quick-apps) | `client.modal.create_comfyui_task(...)` | Query template parameters, create ComfyUI quick-app tasks, and poll results |
| [Image/Video Safety Scan](#imagevideo-safety-scan) | `client.modal.scan_image(...)` | Detect content-safety risks in images, GIFs, or videos |
| [Sensitive-Word Scan](#sensitive-word-scan) | `client.modal.scan_text(...)` | Detect sensitive words and combination-rule risks in text |
| [Text Content Safety Scan](#text-content-safety-scan) | `client.modal.scan_text_content(...)` | Review short text risk level and category label |
| [Visual Structured Text Fusion Scan](#visual-structured-text-fusion-scan) | `client.modal.scan_visual_structured_text_fusion(...)` | Scan digital-human cover images and structured copy together |
| [Face Scan](#face-scan) | `client.modal.scan_face(...)` | Detect face-related results in images or videos |
| [Audio Scan](#audio-scan) | `client.modal.scan_audio(...)` | Detect audio content risks |
| [LLM API](#llm-api) | `client.llm` / `client.LLM` | OpenAI / Anthropic / Responses / Embeddings / Rerank compatible APIs |

## Installation

Install the latest code from GitHub:

```bash
pip install --upgrade git+https://github.com/SeaArt-Infra/sea-sdk-python.git
```

Requirements:

- Python 3.10+

## Initialization

```python
import seaart_sdk as sa

client = sa.Client(
    sa.ClientConfig(
        api_key="sa-your-api-key",
    )
)
```

Configure the unified gateway address through `base_url`. The SDK uses it to call multimodal, LLM, and passthrough capabilities.

```python
client = sa.Client(
    sa.ClientConfig(
        api_key="sa-your-api-key",
        base_url="https://gateway.example.com",
        timeout=60.0,
        project="my-project",
    )
)
```

Keep the selected model in the SDK payload's top-level `model` field. The SDK sends it as the `X-Model` header and removes it from the serialized JSON body. Do not pass `X-Model` with `WithHeader(...)` when the payload already contains `model`.

## Multimodal API

### Model List and Parameter Details

```python
models = client.modal.list_models(
    sa.ModelSearchParams(
        query="",
        limit=2,
    )
)
for hit in models.hits:
    print(hit["name"])

skill = client.modal.get_model_skill("alibaba_animate_anyone_detect")
print(skill)
```

`list_models` / `search_models` supports these query parameters:

- `query` -> `q`
- `input` -> `input`
- `output` -> `output`
- `type` -> `type`
- `provider` -> `provider`
- `limit` -> `limit`

### Generation Tasks

There are two common ways to create a task: pass a raw request dict, or use the `NewTask` typed helper to build the request body. Both ultimately call `client.modal.create(...)`.

**Option 1: Pass a raw request dict**

```python
task = client.modal.create(
    {
        "moderation": True,
        "model": "alibaba_wanx26_i2v_flash",
        "input": [
            {
                "params": {
                    "input": {
                        "img_url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg",
                        "prompt": "A dog and a girl playing happily in an autumn park",
                    },
                    "parameters": {
                        "resolution": "720P",
                        "duration": 5,
                        "prompt_extend": True,
                        "watermark": False,
                    },
                }
            }
        ],
    },
    sa.WithHeader("X-Trace-Id", "trace-123"),
)

print(task.id, task.status)
```

`moderation` is a boolean and optional. `True` enables moderation allowlisting, while `False` disables it.

**Option 2: Build the request body with the typed helper**

```python
body = (
    sa.NewTask("alibaba_wanx26_i2v_flash")
    .moderation(True)
    .params(
        {
            "input": {
                "img_url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg",
                "prompt": "A dog and a girl playing happily in an autumn park",
            },
            "parameters": {
                "resolution": "720P",
                "duration": 5,
                "prompt_extend": True,
                "watermark": False,
            },
        }
    )
    .metadata("trace_id", "trace-123")
    .build()
)

task = client.modal.create(body)
```

`params` passes model parameters. The exact fields depend on the parameter details of the selected model.

**Poll results**

```python
task = client.modal.wait(
    "task_abc123",
    sa.WithPollInterval(3.0),
    sa.WithPollTimeout(300.0),
)

print(task.status, task.progress, task.urls())
```

You can also poll results directly after creating a task:

```python
task = client.modal.create({"model": "alibaba_wanx26_i2v_flash"})
task = task.wait(sa.WithPollInterval(5.0))
```

### ComfyUI Quick Apps

Use the ComfyUI helpers for quick-app templates. Pass one or more `template_id` values to `list_comfyui_templates` to retrieve each template's input fields, allowed values, and defaults. `create_comfyui_task` always routes with `X-Model: comfyui` and builds the required `input[0].params` envelope; pass only the template ID, field values, and optional `high_memory`.

```python
templates = client.modal.list_comfyui_templates(["d32kq8le878c73876j5g"])
for item in templates.templates[0].inputs:
    print(item.field, item.required, item.constraints)

task = client.modal.create_comfyui_task(
    template_id="d32kq8le878c73876j5g",
    inputs=[
        sa.ComfyUIInput(
            field="image",
            value="https://image.cdn2.seaart.me/upload/input.webp",
        ),
        sa.ComfyUIInput(field="select", value=1),
    ],
    high_memory=True,
)
task = task.wait(sa.WithPollInterval(3.0), sa.WithPollTimeout(300.0))
print(task.urls())
```

### Precharge Estimate

The precharge request uses the same parameters as task creation and can estimate costs in advance.
Like task creation, precharge has two common request styles: pass a raw request dict, or build the body with the `NewTask` typed helper. Both ultimately call `client.modal.precharge(...)`.

**Option 1: Pass a raw request dict**

```python
resp = client.modal.precharge(
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

print(resp.status)
print(resp.data.billing_model, resp.data.cost, resp.data.currency)
```

**Option 2: Build the request body with the typed helper**

```python
body = (
    sa.NewTask("volces_seedream_4_5")
    .moderation(False)
    .field("id", "d88pmute87128c73e9r0d0")
    .params(
        {
            "prompt": "A dog",
        }
    )
    .build()
)

resp = client.modal.precharge(body)

print(resp.status)
print(resp.data.billing_model, resp.data.cost, resp.data.currency)
```

**Response example**

```json
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
    "updated_at": 1780633394064
  },
  "status": "success"
}
```

**Field descriptions**

- `status`: Query status. Successful requests return `success`.
- `data.billing_model`: Billing model name.
- `data.cost`: Precharged amount.
- `data.currency`: Currency.
- `data.discount`: Discount factor.
- `data.hash`: Hash of this precharge result.
- `data.model`: Model in the current request.
- `data.original_model`: Original model name.
- `data.sample_count`: Sample count.
- `data.updated_at`: Update timestamp in milliseconds.

If no precharge data is matched, the response may be:

```json
{
  "data": {
    "cost": null,
    "hash": "v1:02833b68895eeb61bf214d35fd669502ef788e4c8d58505893414ae9632ca8ab",
    "model": "volces_seedream_4_5",
    "original_model": "volces_seedream_4_5",
    "reason": "COST_CACHE_MISS"
  },
  "status": "failed"
}
```

In this case, pay attention to:

- `status`: This will be `failed`.
- `data.cost`: May be `null`.
- `data.reason`: Failure reason, such as `COST_CACHE_MISS`.

### Passthrough API (Vendor Passthrough)

The passthrough layer preserves vendor-native API shapes and belongs to the vendor passthrough capability under the multimodal API. Paths must include a vendor prefix, such as `/kling/...`, `/vidu/...`, or `/google/...`.

Passthrough has two common modes: pass a JSON object, or fully pass through the raw request body.

**Option 1: Pass a JSON object**

```python
resp = client.passthrough.post(
    "/kling/v1/videos/text2video",
    {
        "model_name": "kling-v1",
        "prompt": "cinematic shot",
    },
    sa.WithHeader("X-Trace-Id", "trace-123"),
)

print(resp.status_code, resp.body.decode("utf-8"))
```

**Option 2: Pass through a raw request body**

```python
resp = client.passthrough.request_raw(
    "POST",
    "/google/v1beta/models/gemini-2.5-flash-image:generateContent",
    b'{"contents":[{"parts":[{"text":"paint a cat"}]}]}',
)
```

The following convenience methods are also available:

- `request`
- `request_raw`
- `get`
- `post`
- `put`
- `delete`

## Image/Video Safety Scan

The image/video safety scan endpoint is `POST /v1/image/scan`. It detects content-safety risks in images or videos. Provide either a media URL or base64 image content, and use `risk_types` to specify risk categories to detect.

**Image scan example**

```python
result = client.modal.scan_image(
    sa.ImageScanRequest(
        uri="https://example.com/image.jpg",
        risk_types=[
            sa.ImageScanRiskTypePolity,
            sa.ImageScanRiskTypeErotic,
            sa.ImageScanRiskTypeViolent,
            sa.ImageScanRiskTypeChild,
        ],
        detected_age=False,
        is_video=False,
        canary="B",
        scene="avatar",
    )
)

print(result.ok, result.nsfw_level, result.risk_types)
for label in result.label_items:
    print(label.name, label.score, label.risk_type)
```

**Video scan example**

Set `is_video=True` for video scans. Video scans must use `uri` and do not support `img_base64`. If the video duration is known, pass `duration` for billing and statistics.

```python
result = client.modal.scan_image({
    "uri": "https://example.com/video.mp4",
    "risk_types": [sa.ImageScanRiskTypeErotic, sa.ImageScanRiskTypeViolent],
    "is_video": True,
    "duration": 12.5,
})
```

Base64 image content is also supported for image scans:

```python
result = client.modal.scan_image(sa.ImageScanRequest(img_base64="base64-image-content"))
```

To process asynchronously, pass `callback_url`:

```python
result = client.modal.scan_image(
    sa.ImageScanRequest(
        uri="https://example.com/image.jpg",
        callback_url="https://example.com/callback",
        callback_context={"trace_id": "trace-123"},
    )
)
```

**Request fields**

| Field | Type | Required | Description |
|------|------|------|------|
| `uri` | `str` | Conditionally required | Image or video URL to scan. Mutually exclusive with `img_base64`; videos must use `uri` |
| `img_base64` | `str` | Conditionally required | Base64-encoded image content. Mutually exclusive with `uri`; videos are not supported |
| `is_video` | `bool` | No | Whether the file is a video. Defaults to `False` |
| `callback_url` | `str` | Yes for async | Callback URL after detection completes. Only HTTP/HTTPS is supported. Passing this field enables async processing |
| `callback_context` | `dict` | No | Caller passthrough fields. The server does not parse or modify them and returns them unchanged in the callback. Maximum 16KB |
| `risk_types` | `list[str]` | No | Risk categories to detect. If omitted, all risk types are detected |
| `detected_age` | `bool` | No | Whether to perform age detection. Defaults to `False` |
| `canary` | `str` | No | Canary parameter. Defaults to `B` |
| `scene` | `str` | No | Scene identifier used for label-level config lookup and metrics |
| `duration` | `float` | No | Video duration in seconds. Recommended for video scans |

**Response fields**

| Field | Type | Description |
|------|------|------|
| `ok` | `bool` | Whether the scan request completed successfully |
| `nsfw_level` | `int` | Highest risk level. Higher values indicate higher risk |
| `label_items` | `list` | Matched labels. Each item contains `name`, `score`, and `risk_type` |
| `risk_types` | `list[str]` | Risk categories actually matched in this scan |
| `frame_results` | `list` | Per-frame results for video scans. Usually empty for image scans |
| `usage` | `Usage` | Gateway-injected billing metadata |

**Pass response example**

```json
{
  "label_items": [],
  "risk_types": [],
  "usage": {
    "cost": "0.1"
  },
  "ok": true,
  "nsfw_level": 0
}
```

**Risk-hit response example**

```json
{
  "ok": true,
  "nsfw_level": 5,
  "label_items": [
    {
      "name": "Erotic:female nudity:exposed nipples",
      "score": 5,
      "risk_type": "EROTIC"
    },
    {
      "risk_type": "EROTIC",
      "name": "Erotic:nudity:fully exposed buttocks",
      "score": 4
    },
    {
      "name": "Erotic:nudity:covered fully exposed genitals",
      "score": 4,
      "risk_type": "EROTIC"
    },
    {
      "name": "Erotic:sexual suggestion:exposed thighs",
      "score": 1,
      "risk_type": "EROTIC"
    }
  ],
  "risk_types": ["EROTIC"],
  "usage": {
    "cost": "0.1"
  }
}
```

Risk type descriptions:

| Constant | API Value | Description |
|------|--------|------|
| `sa.ImageScanRiskTypePolity` | `POLITY` | Political, public-safety, or related sensitive content |
| `sa.ImageScanRiskTypeErotic` | `EROTIC` | Erotic, nudity, sexually suggestive, or other adult content |
| `sa.ImageScanRiskTypeViolent` | `VIOLENT` | Violence, gore, weapons, harm, or related content |
| `sa.ImageScanRiskTypeChild` | `CHILD` | Child-safety risks, especially unsafe or sexualized child-related content |

## Sensitive-Word Scan

The sensitive-word scan endpoint is `POST /v1/text/scan`. It checks whether prompts or normal text contain sensitive content.

```python
result = client.modal.scan_text(
    sa.TextScanRequest(
        text="a cute cat sitting on the sofa",
        scene=1,
        area_types=[sa.TextScanAreaTypeForeign],
        way=sa.TextScanWayDictionary,
    )
)

print(result.usage)
print(result.status.code, result.status.msg)
print(result.data.is_sensitive)
print(result.data.sensitive_words)
print(result.data.combination)
```

**Request fields**

| Field | Type | Required | Description |
|------|------|------|------|
| `text` | `str` | Yes | Text to scan |
| `scene` | `int` | No | Business scenario defined by the upstream sensitive-word service |
| `area_types` | `list[int]` | No | Regional rule sets. Supports `All`, `Domestic`, and `Foreign` |
| `way` | `int` | No | Checking strategy. Supports dictionary, model, mixed, digital-human, and other strategies |

`area_types` supports `TextScanAreaTypeAll`, `TextScanAreaTypeDomestic`, and `TextScanAreaTypeForeign`. `way` supports `TextScanWayDictionary`, `TextScanWayModel`, `TextScanWayMixed`, and `TextScanWayCharacter`.

**Response fields**

| Field | Type | Description |
|------|------|------|
| `data.sensitive_words` | `list` | Matched sensitive words. Each item contains `word`, `start_index`, `end_index`, and `risk_type_code` |
| `data.combination` | `any` | Upstream combination-rule match details. Usually `null` when there is no match |
| `data.is_sensitive` | `bool` | Whether the text matched sensitive content |
| `status.code` | `int` | Upstream business status code. `10000` means success |
| `status.msg` | `str` | Upstream business status message |
| `status.request_id` | `str` | Upstream request ID |
| `usage` | `Usage` | Gateway-injected billing metadata |

**Pass response example**

```json
{
  "usage": {
    "cost": "1"
  },
  "data": {
    "sensitive_words": [],
    "combination": null,
    "is_sensitive": false
  },
  "status": {
    "msg": "success",
    "request_id": "b5ebfb02a9d11adf98b05b397bd82e9e",
    "code": 10000
  }
}
```

## Text Content Safety Scan

The text content safety scan endpoint is `POST /v1/text/content/scan`. It reviews short text and returns the risk level, category label, and judgment reason. This endpoint does not affect the legacy sensitive-word scan endpoint `POST /v1/text/scan`.

```python
result = client.modal.scan_text_content(
    sa.TextContentScanRequest(
        text="hello world",
        canary="A",
        scene="user_name",
    )
)

print(result.ok, result.level, result.label)
print(result.req_id, result.reason)
print(result.usage)
```

You can also pass a raw request dict:

```python
result = client.modal.scan_text_content(
    {
        "text": "This is a text snippet to review",
        "canary": "A",
        "scene": "seasoul",
    }
)
```

**Request fields**

| Field | Type | Required | Description |
|------|------|------|------|
| `text` | `str` | Yes | Text to review |
| `canary` | `str` | No | Canary branch. `A` means external LLM API with vLLM fallback; `B` means local vLLM |
| `scene` | `str` | No | Business scenario identifier, such as `user_name`, `bio`, `comment`, or `seasoul` |

**Response fields**

| Field | Type | Description |
|------|------|------|
| `ok` | `bool` | Whether the review succeeded |
| `req_id` | `str` | Downstream request ID for tracing; returned for successful reviews and downstream business validation failures |
| `level` | `int` | Risk level from `0` to `6`; higher values indicate higher risk |
| `label` | `str` | Category label in English |
| `reason` | `str` | Judgment reason in English or error reason |
| `usage` | `Usage` | Gateway-injected billing metadata. `usage.cost` is the cost of this call |
| `extra` | `dict` | Upstream fields not modeled by the SDK |

**Pass response example**

```json
{
  "ok": true,
  "req_id": "da49eb3d0b4b4d2cb8a64d2c92d70f81",
  "level": 0,
  "label": "normal",
  "reason": "Neutral greeting expression",
  "usage": {
    "cost": "0.001"
  }
}
```

**Risk-hit response example**

```json
{
  "ok": true,
  "req_id": "6d3597929be847589112510af59c5d2d",
  "level": 5,
  "label": "pornography",
  "reason": "Explicit sexual description",
  "usage": {
    "cost": "0.001"
  }
}
```

## Visual Structured Text Fusion Scan

The visual structured text fusion scan endpoint is `POST /v1/visual/structured/text/fusion/scan`. It evaluates a digital-human cover image together with structured copy. `text_dict` supports nested objects, and image URLs inside it are also scanned.

```python
result = client.modal.scan_visual_structured_text_fusion(
    sa.VisualStructuredTextFusionScanRequest(
        uri="https://example.com/cover.jpg",
        text_dict={
            "name": "Xiaomei",
            "personality": "Gentle and considerate",
            "description": "Enjoys traveling",
            "greeting": "Hello",
        },
        business_type="v1",
        canary="A",
        mode="mixed",
        ocr=1,
    )
)

print(result.ok, result.nsfw_level, result.issue_source, result.risk_keys)
print(result.req_id, result.reason, result.img_reason, result.text_reason)
print(result.usage)
```

`text_dict` is required, and at least one of `uri` and `img_base64` must be provided. If both image inputs are provided, the downstream service prioritizes `img_base64`. Optional fields use downstream defaults when omitted. The downstream service may return HTTP 200 for business validation failures; check `result.ok`.

| Field | Type | Required | Description |
|------|------|------|------|
| `text_dict` | `dict` | Yes | Structured copy, including nested objects and image URLs |
| `img_base64` | `str` | Conditional | Main image base64 without a data URL prefix |
| `uri` | `str` | Conditional | Public image URL or internal storage URI |
| `business_type` | `str` | No | Image small-model business type; downstream default is `v1` |
| `detected_age` | `int` | No | Known age; downstream default is `0` |
| `hash_comparison` | `int` | No | Whether to enable hash comparison; downstream default is `0` |
| `canary` | `str` | No | Canary group; downstream default is `A` |
| `mode` | `str` | No | Detection mode; downstream default is `mixed` |
| `ocr` | `int` | No | Whether to enable OCR; downstream default is `0` |

**Response fields**

| Field | Type | Description |
|------|------|------|
| `ok` | `bool` | Whether the downstream scan completed successfully |
| `nsfw_level` | `int` | Highest risk level across the main image, image/text model, and linked images |
| `reason` | `str` | Combined judgment reason or business validation error |
| `img_reason` | `str` | Image-side risk reason |
| `text_reason` | `str` | Text-side risk reason |
| `issue_source` | `str` | Risk source: `img`, `text`, `both`, or `none` |
| `risk_keys` | `list[str]` | `text_dict` fields that contain risk |
| `req_id` | `str` | Downstream request ID for tracing, including business validation failures |
| `msg` | `str` | Downstream service error message |
| `usage` | `Usage` | Gateway-injected billing metadata |
| `extra` | `dict` | Upstream fields not modeled by the SDK |

## Face Scan

The face scan endpoint is `POST /v1/face/scan`. It detects face-related results in images or videos. You can pass either a media URL or base64 image content.

```python
result = client.modal.scan_face(
    sa.FaceScanRequest(
        uri="https://example.com/image.jpg",
        is_video=0,
        scene="avatar",
    )
)

print(result.ok, result.usage)
print(result.extra)
```

**Request fields**

| Field | Type | Required | Description |
|------|------|------|------|
| `uri` | `str` | Conditionally required | Image or video URL to scan. At least one of `uri` and `img_base64` is required |
| `img_base64` | `str` | Conditionally required | Base64-encoded image content. At least one of `uri` and `img_base64` is required |
| `is_video` | `int` | No | Whether the content is video. Images use `0`; videos use `1` |
| `canary` | `str` | No | Canary or routing marker forwarded to the upstream service |
| `scene` | `str` | No | Business scenario forwarded to the upstream service |
| `duration` | `float` | No | Video duration in seconds. Recommended for video scans |

**Response fields**

| Field | Type | Description |
|------|------|------|
| `ok` | `bool` | Whether the scan request completed successfully |
| `error` | `str` | Upstream business error message. Usually empty on success |
| `usage` | `Usage` | Gateway-injected billing metadata |
| `extra` | `dict` | Upstream fields not modeled by the SDK, such as risk level, labels, face count, and more |

**No-face image response example (SDK return structure)**

```json
{
  "ok": true,
  "error": "",
  "usage": {
    "cost": "1"
  },
  "extra": {
    "nsfw_level": 0,
    "label_items": [],
    "risk_types": []
  }
}
```

**Face image response example (SDK return structure)**

```json
{
  "ok": true,
  "error": "",
  "usage": {
    "cost": "1"
  },
  "extra": {
    "nsfw_level": 0,
    "label_items": [],
    "risk_types": []
  }
}
```

## Audio Scan

The audio scan endpoint is `POST /v1/audio/scan`. It detects risks in audio content. Provide an accessible audio URL. `duration` is used for billing and statistics.

```python
result = client.modal.scan_audio(
    sa.AudioScanRequest(
        uri="https://example.com/audio/test.mp3",
        rec_type="AUDIOPOLITICAL_MOAN_ANTHEN",
        duration=15.0,
    )
)

print(result.risk_level, result.risk_description, result.usage)
for label in result.all_labels:
    print(label.label1, label.label2, label.description)
print(result.extra)
```

**Request fields**

| Field | Type | Required | Description |
|------|------|------|------|
| `uri` | `str` | Yes | Audio URL to scan |
| `rec_type` | `str` | No | Detection type defined by the upstream audio scan service |
| `duration` | `float` | No | Audio duration in seconds. Recommended for billing and statistics |

**Response fields**

| Field | Type | Description |
|------|------|------|
| `risk_description` | `str` | Risk description. Maps to response field `riskDescription` |
| `risk_level` | `str` | Risk level. Maps to response field `riskLevel` |
| `all_labels` | `list` | Matched label list. Maps to response field `allLabels` |
| `usage` | `Usage` | Gateway-injected billing metadata |
| `extra` | `dict` | Upstream fields not modeled by the SDK, such as error code, request ID, and more |

**Pass response example**

```json
{
  "code": 1100,
  "message": "success",
  "requestId": "a63b89046c70435a4fb9a0d36439d0ee",
  "btId": "https://example.com/audio/sample.mp3",
  "detail": {
    "audioDetail": [],
    "audioTags": {},
    "audioText": "sample audio transcription text",
    "audioTime": 4,
    "code": 1100,
    "requestParams": {},
    "riskLevel": "PASS"
  }
}
```

## LLM API

The LLM layer keeps the pattern of request passthrough plus raw response return:

```python
raw = client.llm.chat_completions(
    {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 64,
    },
    sa.WithHeader("X-Trace-Id", "trace-123"),
)

resp = sa.Decode(raw, sa.ChatCompletionResponse)
print(resp.choices[0].message.content)
```

Currently supported methods:

| Method | Description |
|------|------|
| `chat_completions` | Calls an OpenAI Chat Completions-compatible API and returns raw response bytes |
| `chat_completions_stream` | Calls the streaming Chat Completions API and returns iterable SSE stream events |
| `messages` | Calls an Anthropic Messages-compatible API and returns raw response bytes |
| `messages_stream` | Calls the streaming Messages API and returns iterable SSE stream events |
| `responses` | Calls an OpenAI Responses-compatible API and returns raw response bytes |
| `responses_stream` | Calls the streaming Responses API and returns iterable SSE stream events |
| `rerank` | Calls the text reranking API |
| `embeddings` | Calls the embedding generation API |
| `list_models` | Queries the LLM model list |

Streaming response example:

```python
stream = client.llm.chat_completions_stream(
    {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hello"}],
    }
)

for event in stream:
    if event.err:
        raise event.err
    if event.done:
        break
    chunk = sa.Decode(event.data, sa.ChatCompletionResponse)
    print(chunk.choices[0].delta.content)
```

<script
  type="text/plain"
  data-doc-skill
  data-doc-skill-id="seaart-sdk-py"
  data-doc-skill-label="SeaArt Python SDK"
  data-doc-skill-filename="seaart-sdk-py-SKILL.md"
  data-doc-skill-version="1"
>
---
name: seaart-sdk-py
description: Build and troubleshoot SeaArt AI gateway integrations with the seaart-sdk Python client. Use when generating images or videos, calling ComfyUI quick-app templates, searching model skills, estimating multimodal task cost, calling vendor-native passthrough APIs, running media or text safety scans, or using OpenAI- or Anthropic-compatible LLM, streaming, embedding, or rerank APIs.
---

# SeaArt Python SDK

Use `seaart-sdk` to call the SeaArt unified gateway from Python 3.10+. Import it as `seaart_sdk as sa`. The SDK is synchronous and uses only the standard library.

## Install

```bash
pip install --upgrade git+https://github.com/SeaArt-Infra/sea-sdk-python.git
```

## Workflow

1. Initialize one `sa.Client` with the API key and, when required, gateway URL.
2. Select `client.modal` for generation, model skills, precharge, or safety scans; `client.llm` for LLM APIs; and `client.passthrough` for vendor-native paths.
3. For a multimodal model, inspect `client.modal.get_model_skill(model)` before building model-specific `params`.
4. Poll generation tasks with `task.wait(...)`, then use `task.urls()` only after completion.
5. Decode successful LLM bytes or stream event data with `sa.Decode`; catch `sa.SeaArtError` at the request boundary.

## Initialize Client

```python
import seaart_sdk as sa

client = sa.Client(
    sa.ClientConfig(
        api_key="sa-your-api-key",
        base_url="https://gateway.example.com",  # optional
        project="my-project",                    # optional X-Project header
        timeout=60.0,
    )
)
```

Passing `base_url` derives `/model` and `/llm` service URLs. Override `model_base_url`, `llm_base_url`, or `passthrough_base_url` only when services use separate gateways. Do not expose API keys in source control or logs.

Keep the selected model in the SDK payload's top-level `model` field. The SDK sends it as the `X-Model` header and removes it from the serialized JSON body. Do not pass `X-Model` with `sa.WithHeader(...)` when the payload already contains `model`.

## Multimodal Tasks

Search before choosing a model, and retrieve its model skill when exact parameter names matter:

```python
models = client.modal.list_models(sa.ModelSearchParams(query="image", limit=10))
skill = client.modal.get_model_skill("alibaba_wanx26_i2v_flash")
```

Pass the documented model parameters in `input[*].params`, or build the same payload with `sa.NewTask(...)`:

```python
body = (
    sa.NewTask("alibaba_wanx26_i2v_flash")
    .moderation(True)
    .params(
        {
            "input": {
                "img_url": "https://example.com/input.jpg",
                "prompt": "A cinematic mountain sunrise",
            },
            "parameters": {"resolution": "720P", "duration": 5},
        }
    )
    .build()
)

task = client.modal.create(body)
task = task.wait(sa.WithPollInterval(3.0), sa.WithPollTimeout(300.0))
print(task.urls())
```

Use `client.modal.precharge(body)` before a generation request when cost estimation is required. Do not assume every model uses the `input` and `parameters` nesting: follow the result from `get_model_skill`.

## ComfyUI Quick Apps

Retrieve the specification for the supplied `template_id` values before collecting user values. It identifies each template's required fields, input types, allowed values, and defaults. Use `create_comfyui_task` rather than manually constructing the generation body: the SDK fixes the model to `comfyui`, sends it as `X-Model`, and builds `input[0].params`.

```python
templates = client.modal.list_comfyui_templates(["d32kq8le878c73876j5g"])
for item in templates.templates[0].inputs:
    print(item.field, item.required, item.constraints)

task = client.modal.create_comfyui_task(
    template_id="d32kq8le878c73876j5g",
    inputs=[
        sa.ComfyUIInput(
            field="image",
            value="https://image.cdn2.seaart.me/upload/input.webp",
        ),
        sa.ComfyUIInput(field="select", value=1),
    ],
    high_memory=True,
)
task = task.wait(sa.WithPollInterval(3.0), sa.WithPollTimeout(300.0))
print(task.urls())
```

Pass `node_id` in `sa.ComfyUIInput` when a template requires it. `inputs` also accepts equivalent dictionaries with `field` and `value` keys.

## LLM And Streaming APIs

Non-streaming LLM methods return `bytes`. Deserialize them to the matching SDK type:

```python
raw = client.llm.chat_completions(
    {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
    }
)
response = sa.Decode(raw, sa.ChatCompletionResponse)
print(response.choices[0].message.content)
```

Use the dedicated streaming methods rather than setting `stream=True` on non-streaming methods. Stop on `done` and raise an event error:

```python
for event in client.llm.chat_completions_stream(
    {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}]}
):
    if event.err:
        raise event.err
    if event.done:
        break
    chunk = sa.Decode(event.data, sa.ChatCompletionResponse)
    print(chunk.choices[0].delta.content or "", end="")
```

Use `client.llm.messages` / `messages_stream` for Anthropic Messages and `responses` / `responses_stream` for OpenAI Responses. Accumulate their text with `sa.MessagesStreamTextAssembler` or `sa.ResponsesStreamTextAssembler`. Use `embeddings`, `rerank`, and `list_models` for their corresponding LLM endpoints.

## Passthrough, Scans, And Errors

Use passthrough only for a vendor-native path such as `/kling/...`, `/vidu/...`, or `/google/...`; pass a relative path and preserve the returned status, headers, and raw body.

Use the dedicated scan methods for image/video, face, audio, sensitive-word, short-text, or visual-and-structured-text checks. Image and face scans accept either `uri` or `img_base64`; video and audio scans require `uri`.

```python
try:
    result = client.modal.scan_text({"text": "Text to check"})
except sa.SeaArtError as exc:
    if exc.kind in (sa.ERR_AUTH, sa.ERR_QUOTA, sa.ERR_TIMEOUT):
        raise
    raise
```

Handle `ERR_AUTH`, `ERR_QUOTA`, `ERR_TIMEOUT`, `ERR_NETWORK`, and `ERR_TASK_FAILED` explicitly where retries or user feedback differ. For failed multimodal tasks, inspect `SeaArtError.task_id` and the model response before retrying.
</script>
