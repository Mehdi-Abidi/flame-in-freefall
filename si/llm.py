"""Provider-agnostic LLM client for any OpenAI-compatible endpoint (Groq, OpenRouter, Cerebras, NVIDIA).

Configuration comes from environment variables or the project .env file:
    LLM_API_KEY          required
    LLM_BASE_URL         default https://api.groq.com/openai/v1
    LLM_MODEL            default openai/gpt-oss-20b
    LLM_FALLBACK_MODEL   default openai/gpt-oss-120b, used when the main model keeps failing
    LLM_CACHE_DIR        default .cache/llm, set to an empty string to disable caching

Usage:
    from si.llm import LLM
    data = LLM().json("Return {\"ok\": true}")
    python -m si.llm --check
    python -m si.llm "Which diluent suppresses droplet flames better, CO2 or helium?"
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = {
    "LLM_BASE_URL": "https://api.groq.com/openai/v1",
    "LLM_MODEL": "openai/gpt-oss-20b",
    "LLM_FALLBACK_MODEL": "openai/gpt-oss-120b",
    "LLM_CACHE_DIR": str(ROOT / ".cache" / "llm"),
}
RETRYABLE = {408, 409, 425, 429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    pass


def load_env(path=ROOT / ".env"):
    values = {}
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def setting(name, file_values):
    return os.environ.get(name) or file_values.get(name) or DEFAULTS.get(name, "")


def parse_json(text):
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
    if start == -1:
        raise LLMError(f"no JSON in model reply: {text[:200]!r}")
    closing = "}" if text[start] == "{" else "]"
    end = text.rfind(closing)
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as error:
        raise LLMError(f"invalid JSON in model reply: {error}") from error


def model_options(model):
    if model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low"}
    if model.startswith("qwen/") and "qwen3" in model:
        return {"reasoning_format": "hidden"}
    if model.startswith("nvidia/nemotron-3"):
        return {"chat_template_kwargs": {"enable_thinking": False}}
    return {}


class LLM:
    def __init__(self, model=None, base_url=None, api_key=None, fallback_model=None, cache_dir=None,
                 timeout=90, max_retries=4, env_file=ROOT / ".env"):
        file_values = load_env(env_file)
        self.api_key = api_key or setting("LLM_API_KEY", file_values)
        self.base_url = (base_url or setting("LLM_BASE_URL", file_values)).rstrip("/")
        self.model = model or setting("LLM_MODEL", file_values)
        self.fallback_model = fallback_model if fallback_model is not None else setting("LLM_FALLBACK_MODEL", file_values)
        cache = cache_dir if cache_dir is not None else setting("LLM_CACHE_DIR", file_values)
        self.cache_dir = Path(cache) if cache else None
        self.timeout = timeout
        self.max_retries = max_retries
        self.usage = {"calls": 0, "cached": 0, "tokens": 0}
        self.last_model = None
        if not self.api_key:
            raise LLMError("LLM_API_KEY is not set. Add it to .env (see .env.example).")

    def chat(self, messages, json_mode=False, temperature=0.0, max_tokens=2000, system=None):
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        if system:
            messages = [{"role": "system", "content": system}] + messages
        models = [self.model] + ([self.fallback_model] if self.fallback_model and self.fallback_model != self.model else [])
        last_error = None
        for model in models:
            try:
                content = self._complete(model, messages, json_mode, temperature, max_tokens)
                self.last_model = model
                return content
            except LLMError as error:
                last_error = error
        raise last_error

    def json(self, prompt, system=None, max_tokens=2000, temperature=0.0):
        last_error = None
        for _ in range(2):
            reply = self.chat(prompt, json_mode=True, temperature=temperature, max_tokens=max_tokens, system=system)
            try:
                return parse_json(reply)
            except LLMError as error:
                last_error = error
                temperature = 0.2
        raise last_error

    def _complete(self, model, messages, json_mode, temperature, max_tokens):
        body = {"model": model, "messages": messages, "temperature": temperature, "max_completion_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        body.update(model_options(model))
        cache_key = hashlib.sha256(json.dumps([self.base_url, body], sort_keys=True).encode()).hexdigest()
        cached = self._cache_read(cache_key)
        if cached is not None:
            self.usage["cached"] += 1
            return cached
        payload = self._post(body)
        content = (payload.get("choices") or [{}])[0].get("message", {}).get("content")
        if not content:
            raise LLMError(f"{model} returned an empty reply")
        self.usage["calls"] += 1
        self.usage["tokens"] += (payload.get("usage") or {}).get("total_tokens", 0)
        self._cache_write(cache_key, content)
        return content

    def _post(self, body):
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                     "Accept": "application/json", "User-Agent": "flame-in-freefall/0.1"},
        )
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as error:
                detail = error.read()[:300].decode(errors="replace")
                if error.code not in RETRYABLE or attempt == self.max_retries:
                    raise LLMError(f"{body['model']}: HTTP {error.code} {detail}") from error
                time.sleep(self._wait_seconds(error, attempt))
            except (urllib.error.URLError, TimeoutError) as error:
                if attempt == self.max_retries:
                    raise LLMError(f"{body['model']}: network error {error}") from error
                time.sleep(2 ** attempt)
        raise LLMError("unreachable")

    @staticmethod
    def _wait_seconds(error, attempt):
        retry_after = error.headers.get("retry-after") if error.headers else None
        try:
            return min(float(retry_after), 60.0)
        except (TypeError, ValueError):
            return min(2 ** (attempt + 1), 30)

    def _cache_read(self, cache_key):
        if not self.cache_dir:
            return None
        path = self.cache_dir / f"{cache_key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["content"]
        return None

    def _cache_write(self, cache_key, content):
        if not self.cache_dir:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / f"{cache_key}.json").write_text(json.dumps({"content": content}), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Call the configured LLM.")
    parser.add_argument("prompt", nargs="?", help="question to send")
    parser.add_argument("--check", action="store_true", help="verify the key, model and JSON mode")
    parser.add_argument("--model", help="override LLM_MODEL")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        llm = LLM(model=args.model, cache_dir="")
        if args.check or not args.prompt:
            started = time.time()
            reply = llm.json('Reply with this JSON exactly: {"status": "ok", "fuel_phases": ["solid", "liquid", "gas"]}')
            ok = reply.get("status") == "ok"
            print(f"{'OK' if ok else 'UNEXPECTED'}  answered_by={llm.last_model}  requested={llm.model}  base={llm.base_url}  {time.time() - started:.1f}s  reply={reply}")
            sys.exit(0 if ok else 1)
        print(llm.chat(args.prompt))
    except LLMError as error:
        print(f"LLM error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
