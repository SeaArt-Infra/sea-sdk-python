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

默认网关地址为 `https://gateway.example.com`。如果你的环境使用自定义网关，通常只需要覆盖 `base_url`，SDK 会基于同一个网关地址调用不同功能。

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

## 多模态 API

### 模型列表和参数详情

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

### 生成任务

创建任务有两种常用方式：直接传入原始请求 dict，或使用 `NewTask` typed helper 构造请求体。两种方式最终都会调用 `client.modal.create(...)`。

**方式一：直接传入原始请求 dict**

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

**方式二：使用 Typed helper 构造请求体**

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

`params` 用于传入模型参数，具体字段以对应模型的参数详情为准。

**轮询结果**

```python
task = client.modal.wait(
    "task_abc123",
    sa.WithPollInterval(3.0),
    sa.WithPollTimeout(300.0),
)

print(task.status, task.progress, task.urls())
```

也可以在创建任务后直接轮询结果：

```python
task = client.modal.create({"model": "alibaba_wanx26_i2v_flash"})
task = task.wait(sa.WithPollInterval(5.0))
```

### 预扣费查询

预扣费查询请求参数与创建任务相同，可用于提前预估费用。
和创建任务一样，预扣费查询也有两种常用方式：直接传入原始请求 dict，或使用 `NewTask` typed helper 构造请求体。两种方式最终都会调用 `client.modal.precharge(...)`。

**方式一：直接传入原始请求 dict**

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

**方式二：使用 Typed helper 构造请求体**

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

**响应示例**

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

**字段说明**

- `status`：查询状态，成功时为 `success`
- `data.billing_model`：计费模型名
- `data.cost`：预扣费金额
- `data.currency`：币种
- `data.discount`：折扣系数
- `data.hash`：本次预扣费结果哈希
- `data.model`：当前请求模型
- `data.original_model`：原始模型名
- `data.sample_count`：采样数量
- `data.updated_at`：更新时间戳（毫秒）

未匹配上预扣费数据时，可能返回：

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

此时可重点关注：

- `status`：这里会是 `failed`
- `data.cost`：可能为 `null`
- `data.reason`：失败原因，例如 `COST_CACHE_MISS`

### Passthrough API（厂商透传）

Passthrough 层保留厂商原始 API 形态，属于多模态 API 下的厂商透传能力。路径需要带厂商前缀，例如 `/kling/...`、`/vidu/...`、`/google/...`。

Passthrough 有两种常用方式：传入 JSON 对象，或完全透传原始请求体。

**方式一：传入 JSON 对象**

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

**方式二：透传原始请求体**

```python
resp = client.passthrough.request_raw(
    "POST",
    "/google/v1beta/models/gemini-2.5-flash-image:generateContent",
    b'{"contents":[{"parts":[{"text":"paint a cat"}]}]}',
)
```

当前还提供以下便捷方法：

- `request`
- `request_raw`
- `get`
- `post`
- `put`
- `delete`

## 图片/视频鉴黄

图片/视频鉴黄接口对应 `POST /v1/image/scan`，用于对图片、GIF 或视频内容进行安全风险检测。调用时需要提供待检测媒体 URL，并通过 `risk_types` 指定需要检测的风险类型。

**图片检测示例**

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
for label in result.label_items:
    print(label.name, label.score, label.risk_type)
```

**视频检测示例**

视频检测时设置 `is_video=1`。如果已知视频时长，建议传入 `duration`，用于计费和统计。

```python
result = client.modal.scan_image({
    "uri": "https://example.com/video.mp4",
    "risk_types": [sa.ImageScanRiskTypeErotic, sa.ImageScanRiskTypeViolent],
    "is_video": 1,
    "duration": 12.5,
})
```

**请求字段**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `uri` | `str` | 是 | 待检测图片、GIF 或视频 URL |
| `risk_types` | `list[str]` | 否 | 指定检测风险类型；为空时按网关默认策略处理 |
| `detected_age` | `int` | 否 | 是否启用年龄段检测，`1` 表示启用，`0` 表示关闭 |
| `is_video` | `int` | 否 | 是否为视频内容，图片/GIF 为 `0`，视频为 `1` |
| `duration` | `float` | 否 | 视频时长，单位秒；视频检测时建议传入 |

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `ok` | `bool` | 检测请求是否成功完成 |
| `nsfw_level` | `int` | 最高风险等级，数值越高表示风险越高 |
| `label_items` | `list` | 命中的具体标签，每项包含 `name`、`score`、`risk_type` |
| `risk_types` | `list[str]` | 本次检测实际命中的风险类型 |
| `frame_results` | `list` | 视频检测时的逐帧结果，图片检测通常为空 |
| `usage` | `Usage` | 网关注入的计费信息 |

**审核通过响应示例**

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

**命中风险响应示例**

```json
{
  "ok": true,
  "nsfw_level": 5,
  "label_items": [
    {
      "name": "色情:女裸露:女上露点",
      "score": 5,
      "risk_type": "EROTIC"
    },
    {
      "risk_type": "EROTIC",
      "name": "色情:裸露:臀部全裸",
      "score": 4
    },
    {
      "name": "色情:裸露:下体全裸遮点",
      "score": 4,
      "risk_type": "EROTIC"
    },
    {
      "name": "色情:性暗示:大腿裸露",
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

风险类型说明：

| 常量 | 接口值 | 说明 |
|------|--------|------|
| `sa.ImageScanRiskTypePolity` | `POLITY` | 政治敏感、公共安全等风险内容 |
| `sa.ImageScanRiskTypeErotic` | `EROTIC` | 色情、裸露、性暗示等成人内容 |
| `sa.ImageScanRiskTypeViolent` | `VIOLENT` | 暴力、血腥、武器、伤害等内容 |
| `sa.ImageScanRiskTypeChild` | `CHILD` | 儿童安全风险，尤其是儿童相关不安全或性化内容 |

## 敏感词检测

敏感词检测接口对应 `POST /v1/text/scan`，用于检测提示词或普通文本中是否包含敏感内容。

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

**请求字段**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | `str` | 是 | 待检测文本 |
| `scene` | `int` | 否 | 业务场景，由上游敏感词服务定义 |
| `area_types` | `list[int]` | 否 | 区域规则集，支持 `All`、`Domestic`、`Foreign` |
| `way` | `int` | 否 | 检测方式，支持字典、模型、混合、数字人等策略 |

`area_types` 可选 `TextScanAreaTypeAll`、`TextScanAreaTypeDomestic`、`TextScanAreaTypeForeign`。`way` 可选 `TextScanWayDictionary`、`TextScanWayModel`、`TextScanWayMixed`、`TextScanWayCharacter`。

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `data.sensitive_words` | `list` | 命中的敏感词列表，命中项包含 `word`、`start_index`、`end_index`、`risk_type_code` |
| `data.combination` | `any` | 上游组合规则命中详情；未命中时通常为 `null` |
| `data.is_sensitive` | `bool` | 文本是否命中敏感内容 |
| `status.code` | `int` | 上游业务状态码，`10000` 表示成功 |
| `status.msg` | `str` | 上游业务状态信息 |
| `status.request_id` | `str` | 上游请求 ID |
| `usage` | `Usage` | 网关注入的计费信息 |

**审核通过响应示例**

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

## 人脸检测

人脸检测接口对应 `POST /v1/face/scan`，用于检测图片或视频中的人脸相关结果。调用时可以传入媒体 URL，也可以传入图片 base64 内容。

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

**请求字段**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `uri` | `str` | 条件必填 | 待检测图片或视频 URL；`uri` 和 `img_base64` 至少传一个 |
| `img_base64` | `str` | 条件必填 | 图片 base64 内容；`uri` 和 `img_base64` 至少传一个 |
| `is_video` | `int` | 否 | 是否为视频内容，图片为 `0`，视频为 `1` |
| `canary` | `str` | 否 | 灰度或路由标记，透传给上游服务 |
| `scene` | `str` | 否 | 业务场景，透传给上游服务 |
| `duration` | `float` | 否 | 视频时长，单位秒；视频检测时建议传入 |

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `ok` | `bool` | 检测请求是否成功完成 |
| `error` | `str` | 上游业务错误信息；成功时通常为空 |
| `usage` | `Usage` | 网关注入的计费信息 |
| `extra` | `dict` | 上游返回的未建模字段，例如风险等级、标签、人脸数量等 |

**不含人脸图片响应示例**

```json
{
  "nsfw_level": 0,
  "label_items": [],
  "risk_types": [],
  "ok": true,
  "usage": {
    "cost": "1"
  }
}
```

**含人脸图片响应示例**

```json
{
  "usage": {
    "cost": "1"
  },
  "nsfw_level": 0,
  "label_items": [],
  "risk_types": [],
  "ok": true
}
```

## 音频检测

音频检测接口对应 `POST /v1/audio/scan`，用于检测音频内容风险。调用时需要提供可访问的音频 URL，`duration` 用于计费和统计。

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

**请求字段**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `uri` | `str` | 是 | 待检测音频 URL |
| `rec_type` | `str` | 否 | 检测类型，由上游音频检测服务定义 |
| `duration` | `float` | 否 | 音频时长，单位秒；建议传入以便计费和统计 |

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `risk_description` | `str` | 风险描述，对应响应字段 `riskDescription` |
| `risk_level` | `str` | 风险等级，对应响应字段 `riskLevel` |
| `all_labels` | `list` | 命中的标签列表，对应响应字段 `allLabels` |
| `usage` | `Usage` | 网关注入的计费信息 |
| `extra` | `dict` | 上游返回的未建模字段，例如错误码、请求 ID 等 |

**审核通过响应示例**

```json
{
  "code": 1100,
  "message": "成功",
  "requestId": "a63b89046c70435a4fb9a0d36439d0ee",
  "btId": "https://example.com/audio/sample.mp3",
  "detail": {
    "audioDetail": [],
    "audioTags": {},
    "audioText": "示例音频转写文本",
    "audioTime": 4,
    "code": 1100,
    "requestParams": {},
    "riskLevel": "PASS"
  }
}
```

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
