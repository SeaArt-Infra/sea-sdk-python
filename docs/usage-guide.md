# SeaArt Python SDK 使用说明文档

SeaArt Python SDK（`seaart-sdk`）是 SeaArt AI 平台的官方 Python 客户端库，提供多模态任务（图像/视频生成）、厂商透传和 LLM 文本处理能力。

**要求：** Python 3.10+，无第三方依赖

---

## 安装

```bash
pip install seaart-sdk
```

---

## 快速开始

```python
import seaart_sdk as sa

client = sa.Client(sa.ClientConfig(api_key="sa-your-api-key"))
```

---

## 客户端配��

```python
client = sa.Client(
    sa.ClientConfig(
        api_key="sa-your-api-key",                        # 必填：SeaArt API Key
        base_url="https://custom-url.com",                # 可选：自定义基础地址
        model_base_url="https://model-url.com",           # 可选：多模态端点
        llm_base_url="https://llm-url.com",               # 可选：LLM 端点
        passthrough_base_url="https://model-url.com",     # 可选：厂商透传端点，默认同 model_base_url
        project="my-project",                             # 可选：作为 X-Project 头发送
        timeout=60.0,                                     # 可选：默认 300 秒（5 分钟）
    )
)
```

**默认端点：** `https://gateway.example.com`
**认证方式：** `Authorization: Bearer {api_key}`

---

## Modal API（多模态任务）

### 创建任务

```python
task = client.modal.create({
    "moderation": True,
    "model": "alibaba_wanx26_i2v_flash",
    "input": [
        {
            "params": {
                "input": {
                    "img_url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg",
                    "prompt": "小狗和女孩在秋天的公园里快乐地玩耍"
                },
                "parameters": {
                    "resolution": "720P",
                    "duration": 5,
                    "prompt_extend": True,
                    "watermark": False
                }
            },
        }
    ],
})
```

`moderation` 为布尔类型，非必传；`True` 表示开白，`False` 表示非开白。

### 创建任务（Typed helper）

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

不同模型的 `params` 结构可能不同。有些模型使用 `input` / `parameters` 两层嵌套，也有些模型直接把模型字段平铺在 `params` 下，例如：

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

### 等待任务完成

```python
# 方式一：在 task 对象上等待
task = task.wait(
    sa.WithPollInterval(3.0),
    sa.WithPollTimeout(300.0),
    sa.WithPollCallback(lambda status, progress: print(f"状态: {status}, 进度: {progress*100:.1f}%")),
)

# 方式二：通过 client 等待
task = client.modal.wait("task_abc123")
```

**轮询选项：**

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `sa.WithPollInterval(seconds)` | 轮询间隔（秒） | 3.0 |
| `sa.WithPollTimeout(seconds)` | 最大等待时间（秒） | 300.0 |
| `sa.WithPollCallback(fn)` | 进度回调 `fn(status, progress)` | - |

### 预扣费查询

预扣费查询路由为 `/model/v1/generation/precharge`，请求参数与创建任务相同。

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

响应示例：

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

字段说明：

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

Typed helper：

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

### 获取任务结果

```python
# 获取所有输出 URL（快捷方法）
urls = task.urls()

# 遍历详细输出
for output in task.output:
    for content in output.content:
        print(f"类型: {content.type}, URL: {content.url}")
```

### 图片/视频鉴黄

鉴黄接口走 `model_base_url`，对应 `POST /v1/image/scan`，用于图片、GIF 或视频风险检测。

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

视频检测设置 `is_video=1`，可传 `duration`：

```python
result = client.modal.scan_image({
    "uri": "https://example.com/video.mp4",
    "risk_types": [sa.ImageScanRiskTypeErotic, sa.ImageScanRiskTypeViolent],
    "is_video": 1,
    "duration": 12.5,
})
```

风险类型说明：

| 常量 | 接口值 | 说明 |
|------|--------|------|
| `sa.ImageScanRiskTypePolity` | `POLITY` | 政治敏感、公共安全等风险内容 |
| `sa.ImageScanRiskTypeErotic` | `EROTIC` | 色情、裸露、性暗示等成人内容 |
| `sa.ImageScanRiskTypeViolent` | `VIOLENT` | 暴力、血腥、武器、伤害等内容 |
| `sa.ImageScanRiskTypeChild` | `CHILD` | 儿童安全风险，尤其是儿童相关不安全或性化内容 |

### 敏感词检测

敏感词检测接口走 `model_base_url`，对应 `POST /v1/text/scan`。

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

`area_types` 可选 `TextScanAreaTypeAll`、`TextScanAreaTypeDomestic`、`TextScanAreaTypeForeign`。`way` 可选 `TextScanWayDictionary`、`TextScanWayModel`、`TextScanWayMixed`、`TextScanWayCharacter`。敏感词索引 `start_index` / `end_index` 基于 rune 数组；`is_sensitive` 表示整体是否命中敏感内容，`combination` 保留组合规则命中详情，未建模字段会保留在 `extra`。

### 人脸检测

人脸检测接口走 `model_base_url`，对应 `POST /v1/face/scan`，用于图片或视频人脸检测。网关会转发到上游 `/cloud/face/scan`。

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

也可以传 `img_base64`。视频检测设置 `is_video=1`，可传 `duration`。上游返回中的未建模字段会保留在 `extra`。

### 音频检测

音频检测接口走 `model_base_url`，对应 `POST /v1/audio/scan`，用于音频风险检测。网关会转发到下游音频检测服务并注入 `usage` 计费信息。

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
```

`rec_type` 为检测类型，`duration` 为音频时长秒数并用于计费。上游返回中的未建模字段会保留在 `extra`。

**Task 状态：** `"in_progress"` / `"completed"` / `"failed"`

---

## Passthrough API（厂商透传）

用于调用厂商原始 API 形态的接口，路径需要带厂商前缀，例如 `/kling/...`、`/vidu/...`、`/google/...`。

### JSON 请求

```python
resp = client.passthrough.post(
    "/kling/v1/videos/text2video",
    {
        "model_name": "kling-v1",
        "prompt": "cinematic shot",
    },
    sa.WithHeader("X-Trace-Id", "trace-123"),
)

print(resp.status_code)
print(resp.body.decode("utf-8"))
```

### 原始请求体透传

```python
resp = client.passthrough.request_raw(
    "POST",
    "/google/v1beta/models/gemini-2.5-flash-image:generateContent",
    b'{"contents":[{"parts":[{"text":"paint a cat"}]}]}',
)
```

`PassthroughResponse` 会保留响应状态码、响应头和原始 body：

```python
@dataclass
class PassthroughResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes
```

---

## LLM API

> 所有 LLM 方法均为同步调用，返回 `bytes`，使用 `sa.Decode(raw, Type)` 反序列化。

### Chat Completions（OpenAI 兼容）

```python
# 非流式
raw = client.llm.chat_completions({
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 64,
})
resp = sa.Decode(raw, sa.ChatCompletionResponse)
print(resp.choices[0].message.content)

# 流式
stream = client.llm.chat_completions_stream({
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "你好"}],
})
for event in stream:
    if event.err:
        raise event.err
    if event.done:
        break
    chunk = sa.Decode(event.data, sa.ChatCompletionResponse)
    print(chunk.choices[0].delta.content, end="", flush=True)
```

### Messages API（Anthropic 格式）

```python
# 非流式
raw = client.llm.messages({
    "model": "claude-3-5-sonnet",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 64,
})
resp = sa.Decode(raw, sa.MessagesResponse)

# 流式 + 文本组装器
stream = client.llm.messages_stream({
    "model": "claude-3-5-sonnet",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 256,
})
assembler = sa.MessagesStreamTextAssembler()
for event in stream:
    if event.done:
        break
    chunk = sa.Decode(event.data, sa.MessagesStreamChunk)
    assembler.add(chunk)
print(assembler.text())
```

### Responses API

```python
# 非流式
raw = client.llm.responses(payload)
resp = sa.Decode(raw, sa.ResponsesResponse)

# 流式 + 文本组装器
stream = client.llm.responses_stream(payload)
assembler = sa.ResponsesStreamTextAssembler()
for event in stream:
    if event.done:
        break
    chunk = sa.Decode(event.data, sa.ResponsesResponseStreamChunk)
    assembler.add(chunk)
print(assembler.text())
```

### Embeddings

```python
raw = client.llm.embeddings({
    "model": "text-embedding-3-small",
    "input": "需要向量化的文本",
})
resp = sa.Decode(raw, sa.EmbeddingsResponse)
vectors = [obj.embedding for obj in resp.data]
```

### Reranking

```python
raw = client.llm.rerank({
    "model": "rerank-model",
    "query": "搜索查询",
    "documents": ["文档1", "文档2"],
})
resp = sa.Decode(raw, sa.RerankResponse)
for result in resp.results:
    print(f"Index: {result.index}, Score: {result.relevance_score:.4f}")
```

### 列出可用模型

```python
raw = client.llm.list_models()
resp = sa.Decode(raw, sa.LLMModelListResponse)
for model in resp.data:
    print(model.id)
```

---

## 请求选项

```python
client.llm.chat_completions(
    payload,
    sa.WithHeader("X-Trace-Id", "abc-123"),
    sa.WithHeader("X-Tenant-Id", "tenant-a"),
)

# 批量设置
client.modal.create(
    body,
    sa.WithHeaders({"X-Trace-Id": "abc-123", "X-Region": "cn"}),
)
```

---

## 错误处理

```python
from seaart_sdk import SeaArtError

try:
    task = client.modal.create(body)
except SeaArtError as e:
    if e.kind == sa.ERR_AUTH:
        print("API Key 无效或无权限")
    elif e.kind == sa.ERR_QUOTA:
        print("请求频率超限，请稍后重试")
    elif e.kind == sa.ERR_TIMEOUT:
        print("请求超时")
    elif e.kind == sa.ERR_NETWORK:
        print("网络连接错误")
    elif e.kind == sa.ERR_TASK_FAILED:
        print(f"任务执行失败: {e.message}, TaskID: {e.task_id}")
    else:
        print(f"错误: {e.message}")
```

**错误类型常量：**

| 常量 | 触发场景 |
|------|----------|
| `sa.ERR_AUTH` | HTTP 401/403，认证失败 |
| `sa.ERR_QUOTA` | HTTP 429，超出配额/频率限制 |
| `sa.ERR_TIMEOUT` | HTTP 408/504，轮询超时 |
| `sa.ERR_NETWORK` | 网络连接错误 |
| `sa.ERR_TASK_FAILED` | 任务执行失败 |
| `sa.ERR_GENERAL` | 其他错误 |

---

## 完整示例

### 视频生成

```python
import seaart_sdk as sa

client = sa.Client(sa.ClientConfig(api_key="sa-your-api-key"))

# 创建任务
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
    }
)

print(f"任务已创建: {task.id}")

# 等待完成
task = task.wait(
    sa.WithPollCallback(lambda s, p: print(f"\r进度: {p*100:.0f}%", end=""))
)

# 输出结果
for url in task.urls():
    print(f"\n视频 URL: {url}")
```

### LLM 流式对话

```python
import seaart_sdk as sa

client = sa.Client(sa.ClientConfig(api_key="sa-your-api-key"))

stream = client.llm.chat_completions_stream({
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "用一句话介绍 Python 语言"}],
})

for event in stream:
    if event.err:
        raise event.err
    if event.done:
        break
    chunk = sa.Decode(event.data, sa.ChatCompletionResponse)
    if chunk.choices and chunk.choices[0].delta:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()
```
