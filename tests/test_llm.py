import io
import json
import tempfile
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest import mock

from si.llm import LLM, LLMError, model_options, parse_json


def reply(content, tokens=10):
    body = json.dumps({"choices": [{"message": {"content": content}}], "usage": {"total_tokens": tokens}}).encode()
    response = mock.MagicMock()
    response.read.return_value = body
    response.__enter__.return_value = response
    return response


def http_error(code, retry_after=None):
    headers = Message()
    if retry_after is not None:
        headers["retry-after"] = str(retry_after)
    return urllib.error.HTTPError("https://x", code, "error", headers, io.BytesIO(b'{"error":"x"}'))


class ParseJsonTests(unittest.TestCase):
    def test_plain_object(self):
        self.assertEqual(parse_json('{"a": 1}'), {"a": 1})

    def test_fenced_block(self):
        self.assertEqual(parse_json('```json\n{"a": [1, 2]}\n```'), {"a": [1, 2]})

    def test_object_inside_prose(self):
        self.assertEqual(parse_json('Here you go: {"fuel": "heptane"} done.'), {"fuel": "heptane"})

    def test_top_level_list(self):
        self.assertEqual(parse_json('[1, 2, 3]'), [1, 2, 3])

    def test_no_json_raises(self):
        with self.assertRaises(LLMError):
            parse_json("no braces here")


class ModelOptionTests(unittest.TestCase):
    def test_gpt_oss_reasoning_low(self):
        self.assertEqual(model_options("openai/gpt-oss-20b"), {"reasoning_effort": "low"})

    def test_nemotron_thinking_off(self):
        self.assertEqual(model_options("nvidia/nemotron-3.5-lightning-30b-a3b"), {"chat_template_kwargs": {"enable_thinking": False}})

    def test_other_models_plain(self):
        self.assertEqual(model_options("meta-llama/llama-3.3-70b"), {})


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env_file = Path(self.tmp.name) / "missing.env"

    def tearDown(self):
        self.tmp.cleanup()

    def client(self, **kwargs):
        options = {"api_key": "test-key", "base_url": "https://example.test/v1", "model": "openai/gpt-oss-20b",
                   "fallback_model": "", "cache_dir": "", "env_file": self.env_file, "max_retries": 2}
        options.update(kwargs)
        return LLM(**options)

    def test_missing_key_raises(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(LLMError):
                LLM(api_key="", env_file=self.env_file)

    def test_reads_settings_from_env_file(self):
        env_file = Path(self.tmp.name) / ".env"
        env_file.write_text('LLM_API_KEY="from-file"\nLLM_MODEL=openai/gpt-oss-120b\n', encoding="utf-8")
        with mock.patch.dict("os.environ", {}, clear=True):
            llm = LLM(env_file=env_file, cache_dir="")
        self.assertEqual((llm.api_key, llm.model), ("from-file", "openai/gpt-oss-120b"))

    def test_json_request_body(self):
        with mock.patch("urllib.request.urlopen", return_value=reply('{"ok": true}')) as urlopen:
            self.assertEqual(self.client().json("hi"), {"ok": True})
        request = urlopen.call_args[0][0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://example.test/v1/chat/completions")
        self.assertEqual(request.headers["Authorization"], "Bearer test-key")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["reasoning_effort"], "low")
        self.assertEqual(body["temperature"], 0.0)

    def test_retries_rate_limit_then_succeeds(self):
        responses = [http_error(429, retry_after=0), reply("hello")]
        with mock.patch("urllib.request.urlopen", side_effect=responses), mock.patch("time.sleep") as sleep:
            self.assertEqual(self.client().chat("hi"), "hello")
        sleep.assert_called_once_with(0.0)

    def test_does_not_retry_auth_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=[http_error(401)]) as urlopen:
            with self.assertRaises(LLMError):
                self.client().chat("hi")
        self.assertEqual(urlopen.call_count, 1)

    def test_falls_back_to_second_model(self):
        responses = [http_error(400), reply("from fallback")]
        with mock.patch("urllib.request.urlopen", side_effect=responses) as urlopen:
            result = self.client(fallback_model="openai/gpt-oss-120b").chat("hi")
        self.assertEqual(result, "from fallback")
        self.assertEqual(json.loads(urlopen.call_args[0][0].data)["model"], "openai/gpt-oss-120b")

    def test_reports_model_that_answered(self):
        responses = [http_error(404), reply("ok")]
        with mock.patch("urllib.request.urlopen", side_effect=responses):
            llm = self.client(fallback_model="openai/gpt-oss-120b")
            llm.chat("hi")
        self.assertEqual(llm.last_model, "openai/gpt-oss-120b")

    def test_cache_avoids_second_call(self):
        cache = Path(self.tmp.name) / "cache"
        with mock.patch("urllib.request.urlopen", return_value=reply("cached answer")) as urlopen:
            first = self.client(cache_dir=str(cache)).chat("same question")
            second_client = self.client(cache_dir=str(cache))
            second = second_client.chat("same question")
        self.assertEqual((first, second), ("cached answer", "cached answer"))
        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(second_client.usage["cached"], 1)

    def test_invalid_json_is_retried_once(self):
        responses = [reply("not json"), reply('{"fixed": 1}')]
        with mock.patch("urllib.request.urlopen", side_effect=responses):
            self.assertEqual(self.client().json("hi"), {"fixed": 1})


if __name__ == "__main__":
    unittest.main()
