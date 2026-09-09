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
2. Select `client.modal` for generation, model skills, precharge, or safety scans; `client.billing` for team-scoped cost statements; `client.llm` for LLM APIs; and `client.passthrough` for vendor-native paths.
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

For LLM APIs, keep the selected model in the payload's top-level `model` field. The SDK serializes it in the JSON body and does not use `X-Model`; do not pass `X-Model` with `sa.WithHeader(...)` for LLM requests. Multimodal task creation and precharge continue to route their body model through `X-Model`.

## Gateway Context Headers

Gateway API calls require `x-infra-project-id`, `x-infra-af-id`, `x-infra-session-id`, `x-infra-user-id`, and `x-request-id`. These values are request-specific, so create them from the current caller and pass them with `sa.WithHeaders(...)`. `task.wait(...)` does not require these headers.

```python
request_context = sa.WithHeaders({
    "x-infra-project-id": project_id,
    "x-infra-af-id": af_id,
    "x-infra-session-id": session_id,
    "x-infra-user-id": user_id,
    "x-request-id": request_id,
})

raw = client.llm.chat_completions(
    {
        "model": "model-id",
        "messages": [{"role": "user", "content": "Hello"}],
    },
    request_context,
)
```

Pass `request_context` to every direct gateway API call, for example `client.llm.chat_completions(payload, request_context)` and `client.billing.query(query, request_context)`. Reserve `ClientConfig.headers` for client-lifetime constants only.

## Multimodal Tasks

Search before choosing a model, and retrieve its model skill when exact parameter names matter:

```python
models = client.modal.list_models(sa.ModelSearchParams(query="image", limit=10), request_context)
skill = client.modal.get_model_skill("alibaba_wanx26_i2v_flash", request_context)
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

task = client.modal.create(body, request_context)
task = task.wait(sa.WithPollInterval(3.0), sa.WithPollTimeout(300.0))
print(task.urls())
```

Use `client.modal.precharge(body, request_context)` before a generation request when cost estimation is required. Do not assume every model uses the `input` and `parameters` nesting: follow the result from `get_model_skill`.

## Billing Queries

Use `client.billing.query(sa.BillingQuery(...))` for the authenticated team's cost statement. The gateway derives the team from the Bearer token, so callers must not pass `team_alias`. The default environment scope is `develop` plus `release`; set `environment` to one of those values to select a single environment. Use `start`, `end`, `provider`, `credential_name`, `model_group`, `page`, and `page_size` for supported filters.
Use RFC3339 or date-only values for `start`/`end`; the range is `[start, end)`, and omitted values default to the previous seven days.

## ComfyUI Quick Apps

Retrieve the specification for the supplied `template_id` values before collecting user values. It identifies each template's required fields, input types, allowed values, and defaults. Use `create_comfyui_task` rather than manually constructing the generation body: the SDK fixes the model to `comfyui`, sends it as `X-Model`, and builds `input[0].params`.

```python
templates = client.modal.list_comfyui_templates(["d32kq8le878c73876j5g"], request_context)
for item in templates.templates[0].inputs:
    print(item.field, item.required, item.constraints)

task = client.modal.create_comfyui_task(
    "d32kq8le878c73876j5g",
    [
        sa.ComfyUIInput(
            field="image",
            value="https://image.cdn2.seaart.me/upload/input.webp",
        ),
        sa.ComfyUIInput(field="select", value=1),
    ],
    True,
    request_context,
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
    },
    request_context,
)
response = sa.Decode(raw, sa.ChatCompletionResponse)
print(response.choices[0].message.content)
```

Use the dedicated streaming methods rather than setting `stream=True` on non-streaming methods. Stop on `done` and raise an event error:

```python
for event in client.llm.chat_completions_stream(
    {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}]},
    request_context,
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
    result = client.modal.scan_text({"text": "Text to check"}, request_context)
except sa.SeaArtError as exc:
    if exc.kind in (sa.ERR_AUTH, sa.ERR_QUOTA, sa.ERR_TIMEOUT):
        raise
    raise
```

Use `client.modal.scan_character_quality(...)` for character-copy quality and safety review. Send a flat production-line A or B field set; the response exposes `level`, `safety_tag`, and `usage.cost`.

Handle `ERR_AUTH`, `ERR_QUOTA`, `ERR_TIMEOUT`, `ERR_NETWORK`, and `ERR_TASK_FAILED` explicitly where retries or user feedback differ. For failed multimodal tasks, inspect `SeaArtError.task_id` and the model response before retrying.
