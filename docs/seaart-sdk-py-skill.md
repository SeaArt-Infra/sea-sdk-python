---
name: seaart-sdk-py
description: SeaArt Python SDK 使用助手 — 帮助用户用 seaart-sdk 调用 SeaArt AI 平台 API，包括多模态任务（图像/视频生成）、厂商透传和 LLM（对话、流式、embeddings、rerank）
type: slash_command
tags:
  - python
  - seaart
  - sdk
  - llm
  - multimodal
---

当用户触发此技能时，提供 SeaArt Python SDK（`seaart-sdk`）的调用指导。

**触发场景：** 用户需要用 Python 调用 SeaArt API、生成图像/视频、调用 LLM 接口，或遇到 SDK 使用问题时。

**处理逻辑：**

1. 根据用户需求判断使用 Modal API（统一多模态任务）、Passthrough API（厂商原始接口）还是 LLM API（文本生成）
2. 优先推荐 Builder 方式（`sa.NewTask(...).user(...).param(...).build()`）创建 Modal 任务
3. LLM 接口返回 `bytes`，提醒用户用 `sa.Decode(raw, Type)` 反序列化
4. 流式接口推荐配合 `MessagesStreamTextAssembler` / `ResponsesStreamTextAssembler` 使用
5. 错误处理建议捕获 `SeaArtError` 并按 `kind` 属性分类（ERR_AUTH/ERR_QUOTA/ERR_TIMEOUT/ERR_TASK_FAILED）
6. SDK 仅支持同步调用，无 async/await

**输出格式：** 直接给出可运行的 Python 代码片段，附简短说明。代码使用 `import seaart_sdk as sa`。

---

# SeaArt Python SDK 完整参考

SeaArt Python SDK（`seaart-sdk`）是 SeaArt AI 平台的官方 Python 客户端库，提供多模态任务（图像/视频生成）、厂商透传和 LLM 文本处理能力。

**要求：** Python 3.10+，无第三方依赖

## 安装

```bash
pip install seaart-sdk
```

## 客户端配置

```python
import seaart_sdk as sa

client = sa.Client(
    sa.ClientConfig(
        api_key="sa-your-api-key",        # 必填
        base_url="https://...",           # 可选：自定义基础地址
        model_base_url="https://...",     # 可选：多模态端点
        llm_base_url="https://...",       # 可选：LLM 端点
        passthrough_base_url="https://...", # 可选：厂商透传端点，默认同 model_base_url
        project="my-project",            # 可选：X-Project 头
        timeout=60.0,                    # 可选：默认 300 秒
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
    "input": [{
        "type": "message",
        "role": "user",
        "content": [
            {"type": "text", "text": "cinematic shot"},
            {"type": "image_url", "url": "https://example.com/ref.webp"},
        ],
    }],
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
task = task.wait(
    sa.WithPollInterval(3.0),
    sa.WithPollTimeout(300.0),
    sa.WithPollCallback(lambda status, progress: print(f"{progress*100:.0f}%")),
)

# 获取输出 URL
for url in task.urls():
    print(url)
```

**Task 状态：** `"in_progress"` / `"completed"` / `"failed"`

### 图片/视频鉴黄

使用 `client.modal.scan_image` 调用 `model_base_url + /v1/image/scan`。

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
        is_video=0,
    )
)
print(result.ok, result.nsfw_level, result.risk_types)
```

视频检测设置 `is_video=1`，可传 `duration`；响应中的 `frame_results` 包含帧级检测结果。

风险类型说明：

| 常量 | 接口值 | 说明 |
|------|--------|------|
| `sa.ImageScanRiskTypePolity` | `POLITY` | 政治敏感、公共安全等风险内容 |
| `sa.ImageScanRiskTypeErotic` | `EROTIC` | 色情、裸露、性暗示等成人内容 |
| `sa.ImageScanRiskTypeViolent` | `VIOLENT` | 暴力、血腥、武器、伤害等内容 |
| `sa.ImageScanRiskTypeChild` | `CHILD` | 儿童安全风险，尤其是儿童相关不安全或性化内容 |

### 敏感词检测

使用 `client.modal.scan_text` 调用 `model_base_url + /v1/text/scan`。

```python
result = client.modal.scan_text(
    sa.TextScanRequest(
        text="prompt to check",
        scene=1,
        area_types=[1, 2],
        way=2,
        scenes=["prompt"],
    )
)
print(result.usage)
print(result.extra.get("result"))
```

上游返回中的未建模字段会保留在 `extra`，网关注入的计费信息在 `usage`。

### 人脸检测

使用 `client.modal.scan_face` 调用 `model_base_url + /v1/face/scan`。网关会转发到上游 `/cloud/face/scan`。

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

也可以传 `img_base64`。视频检测设置 `is_video=1`，可传 `duration`；上游返回中的未建模字段会保留在 `extra`。

---

## Passthrough API（厂商透传）

路径需要带厂商前缀，例如 `/kling/...`、`/vidu/...`、`/google/...`。

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

完全透传原始 JSON 字节时使用 `request_raw`：

```python
resp = client.passthrough.request_raw(
    "POST",
    "/google/v1beta/models/gemini-2.5-flash-image:generateContent",
    b'{"contents":[{"parts":[{"text":"paint a cat"}]}]}',
)
```

---

## LLM API

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
    if event.err: raise event.err
    if event.done: break
    chunk = sa.Decode(event.data, sa.ChatCompletionResponse)
    print(chunk.choices[0].delta.content, end="", flush=True)
```

### Messages API（Anthropic 格式）

```python
# 流式 + 文本组装器
stream = client.llm.messages_stream({
    "model": "claude-3-5-sonnet",
    "messages": [{"role": "user", "content": "你好"}],
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
    "input": "需要向量化的文本",
})
resp = sa.Decode(raw, sa.EmbeddingsResponse)
```

### Reranking

```python
raw = client.llm.rerank({
    "model": "rerank-model",
    "query": "搜索查询",
    "documents": ["文档1", "文档2"],
})
resp = sa.Decode(raw, sa.RerankResponse)
for r in resp.results:
    print(f"Index: {r.index}, Score: {r.relevance_score:.4f}")
```

### 列出可用模型

```python
raw = client.llm.list_models()
resp = sa.Decode(raw, sa.LLMModelListResponse)
```

---

## 请求选项

```python
client.llm.chat_completions(
    payload,
    sa.WithHeader("X-Trace-Id", "abc-123"),
    sa.WithHeaders({"X-Region": "cn"}),
)
```

---

## 错误处理

```python
from seaart_sdk import SeaArtError

try:
    task = client.modal.create(body)
except SeaArtError as e:
    if e.kind == sa.ERR_AUTH:        # 401/403 — API Key 无效
        ...
    elif e.kind == sa.ERR_QUOTA:     # 429 — 超出频率限制
        ...
    elif e.kind == sa.ERR_TIMEOUT:   # 408/504 — 超时
        ...
    elif e.kind == sa.ERR_NETWORK:   # 网络连接错误
        ...
    elif e.kind == sa.ERR_TASK_FAILED:  # 任务执行失败
        print(e.task_id, e.message)
```

---

## 完整示例：视频生成

```python
import seaart_sdk as sa

client = sa.Client(sa.ClientConfig(api_key="sa-your-api-key"))

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

task = task.wait(
    sa.WithPollCallback(lambda s, p: print(f"\r进度: {p*100:.0f}%", end=""))
)

for url in task.urls():
    print(f"\n视频 URL: {url}")
```
