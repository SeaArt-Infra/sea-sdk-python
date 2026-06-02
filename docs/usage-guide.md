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

### 创建任务（Builder 方式，推荐）

```python
body = (
    sa.NewTask("vidu_q3_reference")
    .user(
        sa.Text("cinematic shot"),
        sa.ImageURL("https://example.com/ref1.webp"),
        sa.ImageURL("https://example.com/ref2.webp"),
    )
    .param("duration", 5)
    .metadata("trace_id", "trace-123")
    .build()
)

task = client.modal.create(body)
```

### 创建任务（原始方式）

```python
task = client.modal.create({
    "model": "vidu_q3_reference",
    "input": [
        {
            "type": "message",
            "role": "user",
            "content": [
                {"type": "text", "text": "cinematic shot"},
                {"type": "image_url", "url": "https://example.com/ref.webp"},
            ],
        }
    ],
    "parameters": {"duration": 5},
})
```

### 内容类型构造器

| 函数 | 说明 |
|------|------|
| `sa.Text(text)` | 文本内容 |
| `sa.ImageURL(url)` | 图片 URL |
| `sa.VideoURL(url)` | 视频 URL |
| `sa.AudioURL(url)` | 音频 URL |
| `sa.FileID(id)` | 文件 ID |

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
print(result.data.sensitive_words)
```

`area_types` 可选 `TextScanAreaTypeAll`、`TextScanAreaTypeDomestic`、`TextScanAreaTypeForeign`。`way` 可选 `TextScanWayDictionary`、`TextScanWayModel`、`TextScanWayMixed`、`TextScanWayCharacter`。敏感词索引 `start_index` / `end_index` 基于 rune 数组，未建模字段会保留在 `extra`。

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
    sa.NewTask("vidu_q3_reference")
    .user(
        sa.Text("一只猫在月光下奔跑，电影级画面"),
        sa.ImageURL("https://example.com/cat.jpg"),
    )
    .param("duration", 5)
    .build()
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
