import importlib
import unittest
from unittest.mock import patch


class DummyResponse:
    def __init__(self, headers=None):
        self.headers = headers or {}


class DummyRateLimitError(Exception):
    def __init__(self, message="rate limited", status_code=429, headers=None, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = DummyResponse(headers=headers or {})
        self.body = body or {}


class DummyOpenAIStatusError(Exception):
    def __init__(self, status_code=402, body=None):
        super().__init__("provider error")
        self.status_code = status_code
        self.body = body or {}


class TestMainRateLimitHelpers(unittest.TestCase):
    def test_is_rate_limit_error_from_status_code(self):
        import app.main as main

        importlib.reload(main)
        exc = DummyRateLimitError()
        self.assertTrue(main._is_rate_limit_error(exc))

    def test_extract_retry_delay_from_headers(self):
        import app.main as main

        importlib.reload(main)
        exc = DummyRateLimitError(headers={"retry-after": "12"})
        self.assertEqual(main._extract_retry_delay_seconds(exc), 12)

    def test_extract_openai_provider_message_from_nested_raw_json(self):
        import app.main as main

        importlib.reload(main)
        exc = DummyRateLimitError(
            body={
                "error": {
                    "message": "Provider returned error",
                    "metadata": {"raw": "{\"error\":\"API key USD spend limit exceeded\"}"},
                }
            }
        )
        self.assertEqual(
            main._extract_openai_provider_message(exc),
            "API key USD spend limit exceeded",
        )

    def test_map_openai_status_error_to_http_402(self):
        import app.main as main

        importlib.reload(main)
        exc = DummyOpenAIStatusError(
            status_code=402,
            body={
                "error": {
                    "message": "Provider returned error",
                    "metadata": {"raw": "{\"error\":\"API key USD spend limit exceeded\"}"},
                }
            },
        )
        with patch("openai.APIStatusError", DummyOpenAIStatusError):
            mapped = main._map_openai_status_error(exc)
        self.assertIsNotNone(mapped)
        self.assertEqual(mapped.status_code, 402)
        self.assertIn("spend limit exceeded", mapped.detail["message"])


if __name__ == "__main__":
    unittest.main()
