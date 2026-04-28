from __future__ import annotations

import unittest

from seaart_sdk import (
    ChatCompletionResponse,
    Decode,
    EmbeddingsResponse,
    ERR_AUTH,
    LLMModelListResponse,
    MessagesStreamChunk,
    MessagesStreamTextAssembler,
    ResponsesResponseStreamChunk,
    ResponsesStreamTextAssembler,
    SeaArtError,
    WithHeader,
)

from test_helpers import json_response, make_client, patch_urlopen, request_headers, request_json, request_path, sse_response


class LLMServiceTests(unittest.TestCase):
    def test_chat_completions(self) -> None:
        def handler(request):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request_path(request), "/chat/completions")
            body = request_json(request)
            self.assertEqual(body["model"], "gpt-4o-mini")
            self.assertEqual(body["reasoning_effort"], "low")
            return json_response(
                200,
                {
                    "id": "chat_123",
                    "model": "gpt-4o-mini",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "hello"},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            raw = client.llm.chat_completions(
                {
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 16,
                    "reasoning_effort": "low",
                }
            )
        response = Decode(raw, ChatCompletionResponse)
        self.assertEqual(response.choices[0].message.content, "hello")

    def test_list_models_custom_headers(self) -> None:
        def handler(request):
            self.assertEqual(request_headers(request)["X-region"], "cn")
            return json_response(
                200,
                {"object": "list", "data": [{"id": "gpt-4o-mini", "object": "model"}]},
            )

        client = make_client()
        with patch_urlopen(handler):
            raw = client.llm.list_models(WithHeader("X-Region", "cn"))
        response = Decode(raw, LLMModelListResponse)
        self.assertEqual(response.data[0].id, "gpt-4o-mini")

    def test_error_classification(self) -> None:
        def handler(request):
            return json_response(401, {"error": {"message": "invalid api key"}})

        client = make_client()
        with patch_urlopen(handler):
            with self.assertRaises(SeaArtError) as context:
                client.llm.list_models()
        self.assertEqual(context.exception.kind, ERR_AUTH)

    def test_chat_completions_stream(self) -> None:
        def handler(request):
            body = request_json(request)
            self.assertTrue(body["stream"])
            return sse_response(
                "event: message\n",
                'data: {"id":"chatcmpl_1","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant","content":"hello"}}]}\n\n',
                "data: [DONE]\n\n",
            )

        client = make_client()
        with patch_urlopen(handler):
            events = list(
                client.llm.chat_completions_stream(
                    {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]}
                )
            )

        self.assertEqual(events[0].event, "message")
        response = Decode(events[0].data, ChatCompletionResponse)
        self.assertEqual(response.choices[0].delta.content, "hello")
        self.assertTrue(events[-1].done)

    def test_messages_stream_chunk_parsing(self) -> None:
        def handler(request):
            return sse_response(
                'data: {"type":"message_start","message":{"id":"msg_1","type":"message","role":"assistant","model":"claude-3-5-sonnet","usage":{"input_tokens":7}}}\n\n',
                'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"hello"}}\n\n',
                'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}\n\n',
                'data: {"type":"message_stop"}\n\n',
                "data: [DONE]\n\n",
            )

        client = make_client()
        with patch_urlopen(handler):
            stream = client.llm.messages_stream(
                {
                    "model": "claude-3-5-sonnet",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 32,
                }
            )
            assembler = MessagesStreamTextAssembler()
            saw_start = False
            saw_stop = False
            for event in stream:
                if event.done:
                    break
                chunk = Decode(event.data, MessagesStreamChunk)
                if chunk.type == "message_start":
                    saw_start = True
                    self.assertEqual(chunk.message.role, "assistant")
                elif chunk.type == "content_block_delta":
                    assembler.add(chunk)
                elif chunk.type == "message_stop":
                    saw_stop = True

        self.assertTrue(saw_start)
        self.assertTrue(saw_stop)
        self.assertEqual(assembler.text(), "hello")

    def test_responses_stream_chunk_parsing(self) -> None:
        def handler(request):
            return sse_response(
                'data: {"type":"response.created","response":{"id":"resp_1","object":"response","model":"gpt-4.1-mini","status":"in_progress","output":[]}}\n\n',
                'data: {"type":"response.output_text.delta","item_id":"msg_1","output_index":0,"content_index":0,"delta":"hello"}\n\n',
                'data: {"type":"response.output_text.delta","item_id":"msg_1","output_index":0,"content_index":0,"delta":" world"}\n\n',
                'data: {"type":"response.completed","response":{"id":"resp_1","object":"response","model":"gpt-4.1-mini","status":"completed","output":[],"usage":{"input_tokens":7,"output_tokens":2,"total_tokens":9}}}\n\n',
                "data: [DONE]\n\n",
            )

        client = make_client()
        with patch_urlopen(handler):
            stream = client.llm.responses_stream({"model": "gpt-4.1-mini", "input": "hello"})
            assembler = ResponsesStreamTextAssembler()
            saw_created = False
            saw_completed = False
            for event in stream:
                if event.done:
                    break
                chunk = Decode(event.data, ResponsesResponseStreamChunk)
                if chunk.type == "response.created":
                    saw_created = True
                    self.assertEqual(chunk.response.id, "resp_1")
                elif chunk.type == "response.output_text.delta":
                    assembler.add(chunk)
                elif chunk.type == "response.completed":
                    saw_completed = True
                    self.assertEqual(chunk.response.usage.total_tokens, 9)

        self.assertTrue(saw_created)
        self.assertTrue(saw_completed)
        self.assertEqual(assembler.text(), "hello world")

    def test_streaming_errors_point_to_stream_methods(self) -> None:
        client = make_client()
        with patch_urlopen(lambda request: self.fail("urlopen should not be called")):
            with self.assertRaises(SeaArtError) as context:
                client.llm.chat_completions(
                    {
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": True,
                    }
                )
        self.assertIn("chat_completions_stream", str(context.exception))

    def test_embeddings(self) -> None:
        def handler(request):
            body = request_json(request)
            self.assertEqual(body["model"], "text-embedding-3-small")
            return json_response(
                200,
                {
                    "object": "list",
                    "model": "text-embedding-3-small",
                    "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
                },
            )

        client = make_client()
        with patch_urlopen(handler):
            raw = client.llm.embeddings({"model": "text-embedding-3-small", "input": "hello"})
        response = Decode(raw, EmbeddingsResponse)
        self.assertEqual(len(response.data), 1)


if __name__ == "__main__":
    unittest.main()
