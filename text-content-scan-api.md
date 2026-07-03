# Text Content Safety Scan API

## Endpoint

```http
POST /v1/text/content/scan
```

Reviews short text for content safety and returns whether the review succeeded, the risk level, category label, and judgment reason.

This is a new text content safety scan endpoint. The legacy sensitive-word scan endpoint `POST /v1/text/scan` remains unchanged.

## Authentication

Uses unified gateway authentication.

| Header | Description | Required |
|--------|-------------|----------|
| `X-Gateway-Auth-Token` | Internal gateway authentication token. | Yes |
| `X-User-ID` | User ID. | Yes |
| `Authorization` | `Bearer <api_key>`. | Yes |
| `Content-Type` | `application/json`. | Yes |

## Request Parameters

### Body

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | Yes | - | Text to review. |
| `canary` | string | No | `"A"` | Canary branch. `A` means external LLM API with vLLM fallback; `B` means local vLLM. |
| `scene` | string | No | `""` | Business scenario identifier, such as `user_name`, `bio`, `comment`, or `seasoul`. |

### Request Example

```json
{
  "text": "text to review",
  "canary": "A",
  "scene": "seasoul"
}
```

## Response Format

When the gateway successfully forwards the request downstream, the HTTP status code is `200`. The gateway forwards the downstream response and appends `usage.cost`.

### Normal Content

```json
{
  "ok": true,
  "level": 0,
  "label": "normal",
  "reason": "Neutral greeting expression",
  "usage": {
    "cost": "0.001"
  }
}
```

### Risky Content

```json
{
  "ok": true,
  "level": 5,
  "label": "pornography",
  "reason": "Explicit sexual description",
  "usage": {
    "cost": "0.001"
  }
}
```

### Empty Text

```json
{
  "ok": false,
  "level": 0,
  "label": "",
  "reason": "text cannot be empty",
  "usage": {
    "cost": "0.001"
  }
}
```

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `ok` | bool | Whether the review succeeded. |
| `level` | int | Risk level from `0` to `6`; higher values indicate higher risk. |
| `label` | string | English category label. |
| `reason` | string | Judgment reason or error reason. |
| `usage.cost` | string | Cost of this call in SeaArt Credits. |

## Risk Levels

| Level | Meaning | Example Labels |
|-------|---------|----------------|
| 0 | Fully safe | `normal`, `positive_political`, `protection_education_minors`, `normal_child` |
| 1 | Mildly suggestive | `sexiness` |
| 3 | Sexy content or commercial promotion | `sexual_innuendo`, `commercial_promotion` |
| 4 | Sexual innuendo, insult, or uncomfortable content | `uncomfortable`, `personal_attack`, `group_discrimination`, `violation` |
| 5 | Pornographic or illegal content | `description_illegal`, `illegal_trade_information`, `pornography`, `illegal`, `extremely_bloody`, `incitement_crime` |
| 6 | Zero-tolerance content | `extreme_violence_terrorism`, `porn_minors`, `violation_minors`, `negative_political` |

## Error Responses

### Authentication Failure

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid gateway authentication token"
  }
}
```

### Invalid Request Body

```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "Invalid request body"
  }
}
```

### Service Not Configured

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Text content scan service not configured"
  }
}
```

### Downstream Connection Failure

```json
{
  "error": {
    "code": "BAD_GATEWAY",
    "message": "Failed to connect to text content scan service"
  }
}
```

## Billing

| Item | Description |
|------|-------------|
| Model name | `moderation_text` |
| Billing method | Per call |
| Returned field | `usage.cost` |

## Usage Examples

### cURL

```bash
curl -X POST https://api.seaart.ai/v1/text/content/scan \
  -H "X-Gateway-Auth-Token: <gateway_token>" \
  -H "X-User-ID: <user_id>" \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "hello world",
    "canary": "A",
    "scene": "user_name"
  }'
```

### Python

```python
import requests

url = "https://api.seaart.ai/v1/text/content/scan"
headers = {
    "X-Gateway-Auth-Token": "<gateway_token>",
    "X-User-ID": "<user_id>",
    "Authorization": "Bearer <api_key>",
    "Content-Type": "application/json",
}
payload = {
    "text": "hello world",
    "canary": "A",
    "scene": "user_name",
}

response = requests.post(url, json=payload, headers=headers)
result = response.json()
print(result)
```

## Environment Configuration

Gateway configuration item: `TextContentScanUrl`

| Environment | Gateway Configuration Value | Downstream Request URL |
|-------------|-----------------------------|------------------------|
| Test | `http://aiart-text-inference.gpu-service.dev.seaart.dev` | `http://aiart-text-inference.gpu-service.dev.seaart.dev/text_scan` |
| Production | `http://aiart-text-inference.ingress.gpu-service.production.private.seaart.ai` | `http://aiart-text-inference.ingress.gpu-service.production.private.seaart.ai/text_scan` |

## Notes

1. This endpoint is new and does not affect the legacy `POST /v1/text/scan` endpoint.
2. If `canary` is omitted, downstream defaults decide the branch.
3. `scene` should be a stable business source identifier so downstream services can distinguish call scenarios.
