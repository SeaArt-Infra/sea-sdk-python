# seaart-sdk

SeaArt AI 平台 Python SDK，按 `seaart_sdk_go` 的公开接口翻译实现，当前提供三类能力：

- `client.modal` / `client.Modal`：多模态任务接口
- `client.llm` / `client.LLM`：LLM 透传接口
- `client.passthrough` / `client.Passthrough`：厂商原始 API 透传接口

特点：

- 纯标准库实现，无第三方运行时依赖
- 保留原始请求透传能力
- 支持 SSE 流式响应解析
- 支持任务轮询和通用 task builder

## 安装

本地开发：

```bash
pip install -e .
```

要求：

- Python 3.10+

## 初始化

```python
import seaart_sdk as sa

client = sa.Client(
    sa.ClientConfig(
        api_key="sa-your-api-key",
    )
)
```

默认网关配置：

- `base_url`: `https://gateway.example.com`
- `model_base_url`: `https://gateway.example.com/model`
- `llm_base_url`: `https://gateway.example.com/llm`
- `passthrough_base_url`: `https://gateway.example.com/model`

也可以分别覆盖：

```python
client = sa.Client(
    sa.ClientConfig(
        api_key="sa-your-api-key",
        base_url="https://gateway.example.com",
        model_base_url="https://mm-gateway.example.com",
        llm_base_url="https://llm-gateway.example.com",
        passthrough_base_url="https://mm-gateway.example.com",
        timeout=60.0,
        project="my-project",
    )
)
```

## Modal API

原始透传请求：

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
                        "prompt": "小狗和女孩在秋天的公园里快乐地玩耍",
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

`moderation` 为布尔类型，非必传；`True` 表示开白，`False` 表示非开白。

等待任务完成：

```python
task = client.modal.wait(
    "task_abc123",
    sa.WithPollInterval(3.0),
    sa.WithPollTimeout(300.0),
)

print(task.status, task.progress, task.urls())
```

也可以在创建后继续等待：

```python
task = client.modal.create({"model": "alibaba_wanx26_i2v_flash"})
task = task.wait(sa.WithPollInterval(5.0))
```

Typed helper：

```python
body = (
    sa.NewTask("alibaba_wanx26_i2v_flash")
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
    .metadata("trace_id", "trace-123")
    .build()
)

task = client.modal.create(body)
```

也有些模型会直接把模型字段平铺在 `params` 下：

```python
body = (
    sa.NewTask("grok_imagine_image")
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

task = client.modal.create(body)
```


模型列表和参数详情：

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

`list_models` / `search_models` 支持的查询参数：

- `query` -> `q`
- `input` -> `input`
- `output` -> `output`
- `type` -> `type`
- `provider` -> `provider`
- `limit` -> `limit`

图片/视频鉴黄：

鉴黄接口复用 `model_base_url`，对应 `POST /v1/image/scan`。请求会通过 openresty 转发到 inference-gateway。

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
        detected_age=0,
        is_video=0,
    )
)

print(result.ok, result.nsfw_level, result.risk_types)
```

也可以直接传 dict。视频检测时设置 `is_video=1`，并可传 `duration` 用于计费：

```python
result = client.modal.scan_image({
    "uri": "https://example.com/video.mp4",
    "risk_types": [sa.ImageScanRiskTypeErotic, sa.ImageScanRiskTypeViolent],
    "is_video": 1,
    "duration": 12.5,
})
```

常用响应字段包括 `ok`、`nsfw_level`、`label_items`、`risk_types`、`frame_results` 和 `usage`。

风险类型说明：

| 常量 | 接口值 | 说明 |
|------|--------|------|
| `sa.ImageScanRiskTypePolity` | `POLITY` | 政治敏感、公共安全等风险内容 |
| `sa.ImageScanRiskTypeErotic` | `EROTIC` | 色情、裸露、性暗示等成人内容 |
| `sa.ImageScanRiskTypeViolent` | `VIOLENT` | 暴力、血腥、武器、伤害等内容 |
| `sa.ImageScanRiskTypeChild` | `CHILD` | 儿童安全风险，尤其是儿童相关不安全或性化内容 |

敏感词检测：

敏感词检测接口复用 `model_base_url`，对应 `POST /v1/text/scan`。

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

`area_types` 可选 `TextScanAreaTypeAll`、`TextScanAreaTypeDomestic`、`TextScanAreaTypeForeign`。`way` 可选 `TextScanWayDictionary`、`TextScanWayModel`、`TextScanWayMixed`、`TextScanWayCharacter`。敏感词索引 `start_index` / `end_index` 基于 rune 数组；`is_sensitive` 表示整体是否命中敏感内容，`combination` 保留组合规则命中详情，网关注入的计费信息在 `result.usage`。

人脸检测：

人脸检测接口复用 `model_base_url`，对应 `POST /v1/face/scan`，由 openresty 转发到 inference-gateway，再转发到上游 `/cloud/face/scan`。

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

也可以传 `img_base64`。视频检测时设置 `is_video=1`，并可传 `duration` 用于计费。上游人脸检测返回结构会保留在 `result.extra`，网关注入的计费信息在 `result.usage`。

## Passthrough API

Passthrough 层保留厂商原始 API 形态。路径需要带厂商前缀，例如 `/kling/...`、`/vidu/...`、`/google/...`。

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

如果要完全透传原始 JSON 字节，使用 `request_raw`：

```python
resp = client.passthrough.request_raw(
    "POST",
    "/google/v1beta/models/gemini-2.5-flash-image:generateContent",
    b'{"contents":[{"parts":[{"text":"paint a cat"}]}]}',
)
```

当前提供：

- `request`
- `request_raw`
- `get`
- `post`
- `put`
- `delete`

## LLM API

LLM 层保持“请求透传 + 原始响应返回”的形式：

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

当前支持：

- `chat_completions`
- `chat_completions_stream`
- `messages`
- `messages_stream`
- `responses`
- `responses_stream`
- `rerank`
- `embeddings`
- `list_models`

流式响应示例：

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

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 发布

本地打包与检查：

```bash
make check
```

发布到默认 `twine` 仓库配置：

```bash
make release
```

发布到 GitLab Package Registry：

```bash
make release-gitlab \
  TWINE_REPOSITORY_URL="https://<gitlab-host>/api/v4/projects/<project_id>/packages/pypi" \
  TWINE_USERNAME="__token__" \
  TWINE_PASSWORD="<token>"
```

GitLab CI 已配置为在打 tag 时自动构建并发布到当前项目的 Package Registry：

```bash
git tag v0.1.0
git push origin v0.1.0
```
