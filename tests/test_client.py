from __future__ import annotations

import unittest

from seaart_sdk import (
    DEFAULT_BASE_URL,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_MODEL_BASE_URL,
    DEFAULT_PASSTHROUGH_BASE_URL,
    Client,
    ClientConfig,
    SeaArtError,
)


class ClientInitTests(unittest.TestCase):
    def test_default_base_urls(self) -> None:
        client = Client(ClientConfig(api_key="test-key"))
        self.assertEqual(client.base_url, DEFAULT_BASE_URL)
        self.assertEqual(client.model_base_url, DEFAULT_MODEL_BASE_URL)
        self.assertEqual(client.llm_base_url, DEFAULT_LLM_BASE_URL)
        self.assertEqual(client.passthrough_base_url, DEFAULT_PASSTHROUGH_BASE_URL)

    def test_derives_service_base_urls_from_base_url(self) -> None:
        client = Client(ClientConfig(api_key="test-key", base_url="https://gateway.example.com/"))
        self.assertEqual(client.base_url, "https://gateway.example.com")
        self.assertEqual(client.model_base_url, "https://gateway.example.com/model")
        self.assertEqual(client.llm_base_url, "https://gateway.example.com/llm")
        self.assertEqual(client.passthrough_base_url, "https://gateway.example.com/model")

    def test_service_base_url_overrides(self) -> None:
        client = Client(
            ClientConfig(
                api_key="test-key",
                base_url="https://gateway.example.com",
                model_base_url="https://model.example.com",
                llm_base_url="https://llm.example.com",
                passthrough_base_url="https://passthrough.example.com",
            )
        )
        self.assertEqual(client.model_base_url, "https://model.example.com")
        self.assertEqual(client.llm_base_url, "https://llm.example.com")
        self.assertEqual(client.passthrough_base_url, "https://passthrough.example.com")

    def test_invalid_base_url(self) -> None:
        with self.assertRaises(SeaArtError):
            Client(ClientConfig(api_key="test-key", base_url="://bad"))

    def test_nil_config_uses_defaults(self) -> None:
        client = Client()
        self.assertEqual(client.base_url, DEFAULT_BASE_URL)
        self.assertIsNotNone(client.modal)
        self.assertIsNotNone(client.llm)
        self.assertIsNotNone(client.passthrough)


if __name__ == "__main__":
    unittest.main()
