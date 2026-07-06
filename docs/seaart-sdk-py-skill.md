---
name: seaart-sdk-py
description: SeaArt Python SDK assistant — helps users call SeaArt AI platform APIs with seaart-sdk, including multimodal tasks (image/video generation), vendor passthrough, and LLMs (chat, streaming, embeddings, rerank)
type: slash_command
tags:
  - python
  - seaart
  - sdk
  - llm
  - multimodal
---

When this skill is triggered, provide usage guidance for the SeaArt Python SDK (`seaart-sdk`).

**Scenario:** Use when the user needs to call SeaArt APIs from Python, generate images/videos, call LLM APIs, or troubleshoot SDK usage.

**Workflow:**

1. Choose Modal API (unified multimodal tasks), Passthrough API (vendor-native APIs), or LLM API (text generation) based on the user request
2. Prefer the direct `input[*].params` structure; for typed construction, use `sa.NewTask(...).moderation(...).params({...}).build()`
3. LLM APIs return `bytes`; remind users to deserialize with `sa.Decode(raw, Type)`
4. For streaming APIs, recommend using `MessagesStreamTextAssembler` / `ResponsesStreamTextAssembler`
5. For error handling, recommend catching `SeaArtError` and branching by the `kind` attribute (ERR_AUTH/ERR_QUOTA/ERR_TIMEOUT/ERR_TASK_FAILED)
6. The SDK only supports synchronous calls; there is no async/await API

**Output format:** Provide runnable Python snippets with brief explanations. Use `import seaart_sdk as sa`.

---

# SeaArt Python SDK Complete Reference

SeaArt Python SDK (`seaart-sdk`) is the official Python client for the SeaArt AI platform. It provides multimodal tasks (image/video generation), vendor passthrough, and LLM text processing capabilities.

**Requirements:** Python 3.10+, no third-party dependencies

## Installation

```bash
pip install seaart-sdk
```

## Client Configuration

```python
import seaart_sdk as sa

client = sa.Client(
    sa.ClientConfig(
        api_key="sa-your-api-key",        # Required
        base_url="https://...",           # Optional: custom base URL
        model_base_url="https://...",     # Optional: multimodal endpoint
        llm_base_url="https://...",       # Optional: LLM endpoint
        passthrough_base_url="https://...", # Optional: vendor passthrough endpoint, defaults to model_base_url
        project="my-project",            # Optional: X-Project header
        timeout=60.0,                    # Optional: default 300 seconds
    )
)
```

**Default endpoint:** `https://gateway.example.com`
**Authentication:** `Authorization: Bearer {api_key}`

---

## Modal API (Multimodal Tasks)

### Create task

```python
task = client.modal.create({
    "moderation": True,
    "model": "alibaba_wanx26_i2v_flash",
    "input": [{
        "params": {
            "input": {
                "img_url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg",
                "prompt": "A dog and a girl playing happily in an autumn park"
            },
            "parameters": {
                "resolution": "720P",
                "duration": 5,
                "prompt_extend": True,
                "watermark": False
            },
        }
    }],
})
```

`moderation` is a boolean and optional. `True` enables moderation allowlisting, while `False` disables it.

### Create task (Typed helper)

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

Some models place fields directly under `params` instead of splitting them into `input` / `parameters`:

```python
body = (
    sa.NewTask("grok_imagine_image")
    .field("dash_scope", True)
    .moderation(True)
    .params(
        {
            "aspect_ratio": "1:2",
            "prompt": "Lego art version of Superman and Batman, Night scene",
            "n": 1,
            "resolution": "1k",
        }
    )
    .build()
)

task = client.modal.create(body)
```

### Wait for Task Completion

```python
task = task.wait(
    sa.WithPollInterval(3.0),
    sa.WithPollTimeout(300.0),
    sa.WithPollCallback(lambda status, progress: print(f"{progress*100:.0f}%")),
)

# Get output URLs
for url in task.urls():
    print(url)
```

**Task status:** `"in_progress"` / `"completed"` / `"failed"`

### Precharge Estimate

The precharge route is `/model/v1/generation/precharge`, and its request parameters are the same as task creation.

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

Response example:

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

Field descriptions:

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

Typed helper:

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

### Image/Video Safety Scan

Use `client.modal.scan_image` to call `model_base_url + /v1/image/scan`. Pass either `uri` or `img_base64`; videos must use `uri`.

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
        is_video=False,
        canary="B",
        scene="avatar",
    )
)
print(result.ok, result.nsfw_level, result.risk_types)
```

For video scans, set `is_video=True` and optionally pass `duration`; `frame_results` in the response contains frame-level scan results. Video scans must use `uri`. For image scans, `img_base64` is also supported. Pass `callback_url` to enable async processing; `callback_context` is returned unchanged in the callback.

Risk type descriptions:

| Constant | API Value | Description |
|------|--------|------|
| `sa.ImageScanRiskTypePolity` | `POLITY` | Political, public-safety, or related sensitive content |
| `sa.ImageScanRiskTypeErotic` | `EROTIC` | Erotic, nudity, sexually suggestive, or other adult content |
| `sa.ImageScanRiskTypeViolent` | `VIOLENT` | Violence, gore, weapons, harm, or related content |
| `sa.ImageScanRiskTypeChild` | `CHILD` | Child-safety risks, especially unsafe or sexualized child-related content |

### Sensitive-Word Scan

Use `client.modal.scan_text` to call `model_base_url + /v1/text/scan`.

```python
result = client.modal.scan_text(
    sa.TextScanRequest(
        text="prompt to check",
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

`area_types` supports `TextScanAreaTypeAll`, `TextScanAreaTypeDomestic`, and `TextScanAreaTypeForeign`. `way` supports `TextScanWayDictionary`, `TextScanWayModel`, `TextScanWayMixed`, and `TextScanWayCharacter`. Sensitive-word indexes `start_index` / `end_index` are based on rune arrays. `is_sensitive` indicates whether the whole text matched sensitive content. `combination` keeps combination-rule match details. Unmodeled fields are preserved in `extra`.


### Text Content Safety Scan

Use `client.modal.scan_text_content` to call `model_base_url + /v1/text/content/scan`. This endpoint reviews short text for content safety and does not affect the legacy sensitive-word API `client.modal.scan_text`.

```python
result = client.modal.scan_text_content(
    sa.TextContentScanRequest(
        text="hello world",
        canary="A",
        scene="user_name",
    )
)
print(result.ok, result.level, result.label)
print(result.reason, result.usage)
```

`TextContentScanRequest` contains required `text` plus optional `canary` and `scene`. `TextContentScanResponse` contains `ok`, `level`, `label`, `reason`, `usage`, and unmodeled fields in `extra`.

### Face Scan

Use `client.modal.scan_face` to call `model_base_url + /v1/face/scan`. The gateway forwards the request to upstream `/cloud/face/scan`.

```python
result = client.modal.scan_face(
    sa.FaceScanRequest(
        uri="https://example.com/image.jpg",
        is_video=0,
        scene="avatar",
    )
)
print(result.ok, result.usage)
print(result.extra.get("face_count"))
```

You can also pass `img_base64`. For video scans, set `is_video=1` and optionally pass `duration`; unmodeled upstream response fields are preserved in `extra`.

---

## Passthrough API (Vendor Passthrough)

Paths must include a vendor prefix, such as `/kling/...`, `/vidu/...`, or `/google/...`.

```python
resp = client.passthrough.post(
    "/kling/v1/videos/text2video",
    {
        "model_name": "kling-v1",
        "prompt": "cinematic shot",
    },
)
print(resp.status_code, resp.body.decode("utf-8"))
```

Use `request_raw` when fully passing through raw JSON bytes:

```python
resp = client.passthrough.request_raw(
    "POST",
    "/google/v1beta/models/gemini-2.5-flash-image:generateContent",
    b'{"contents":[{"parts":[{"text":"paint a cat"}]}]}',
)
```

---

## LLM API

### Chat Completions (OpenAI Compatible)

```python
# Non-streaming
raw = client.llm.chat_completions({
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "hello"}],
    "max_tokens": 64,
})
resp = sa.Decode(raw, sa.ChatCompletionResponse)
print(resp.choices[0].message.content)

# Streaming
stream = client.llm.chat_completions_stream({
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "hello"}],
})
for event in stream:
    if event.err: raise event.err
    if event.done: break
    chunk = sa.Decode(event.data, sa.ChatCompletionResponse)
    print(chunk.choices[0].delta.content, end="", flush=True)
```

### Messages API (Anthropic Format)

```python
# Streaming + text assembler
stream = client.llm.messages_stream({
    "model": "claude-3-5-sonnet",
    "messages": [{"role": "user", "content": "hello"}],
    "max_tokens": 256,
})
assembler = sa.MessagesStreamTextAssembler()
for event in stream:
    if event.done: break
    chunk = sa.Decode(event.data, sa.MessagesStreamChunk)
    assembler.add(chunk)
print(assembler.text())
```

### Responses API

```python
stream = client.llm.responses_stream(payload)
assembler = sa.ResponsesStreamTextAssembler()
for event in stream:
    if event.done: break
    chunk = sa.Decode(event.data, sa.ResponsesResponseStreamChunk)
    assembler.add(chunk)
print(assembler.text())
```

### Embeddings

```python
raw = client.llm.embeddings({
    "model": "text-embedding-3-small",
    "input": "text to embed",
})
resp = sa.Decode(raw, sa.EmbeddingsResponse)
```

### Reranking

```python
raw = client.llm.rerank({
    "model": "rerank-model",
    "query": "search query",
    "documents": ["document 1", "document 2"],
})
resp = sa.Decode(raw, sa.RerankResponse)
for r in resp.results:
    print(f"Index: {r.index}, Score: {r.relevance_score:.4f}")
```

### List Available Models

```python
raw = client.llm.list_models()
resp = sa.Decode(raw, sa.LLMModelListResponse)
```

---

## Request Options

```python
client.llm.chat_completions(
    payload,
    sa.WithHeader("X-Trace-Id", "abc-123"),
    sa.WithHeaders({"X-Region": "cn"}),
)
```

---

## Error Handling

```python
from seaart_sdk import SeaArtError

try:
    task = client.modal.create(body)
except SeaArtError as e:
    if e.kind == sa.ERR_AUTH:        # 401/403 — invalid API key
        ...
    elif e.kind == sa.ERR_QUOTA:     # 429 — rate limit exceeded
        ...
    elif e.kind == sa.ERR_TIMEOUT:   # 408/504 — timeout
        ...
    elif e.kind == sa.ERR_NETWORK:   # Network connection error
        ...
    elif e.kind == sa.ERR_TASK_FAILED:  # Task execution failed
        print(e.task_id, e.message)
```

---

## Complete Examples: Video Generation

```python
import seaart_sdk as sa

client = sa.Client(sa.ClientConfig(api_key="sa-your-api-key"))

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
    }
)

print(f"Task created: {task.id}")

task = task.wait(
    sa.WithPollCallback(lambda s, p: print(f"\rProgress: {p*100:.0f}%", end=""))
)

for url in task.urls():
    print(f"\nVideo URL: {url}")
```
