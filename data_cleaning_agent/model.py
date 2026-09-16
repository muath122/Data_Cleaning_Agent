"""One local model client shared by all role prompts."""

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


class ModelError(RuntimeError):
    pass


def load_prompt(role: str) -> str:
    if role not in {"schema", "structured", "categories", "text", "validation", "adaptive"}:
        raise ValueError("Unknown role")
    return (PROMPT_DIR / f"{role}.md").read_text(encoding="utf-8")


class LocalModel:
    def __init__(self, base_url=None, model=None, *, transport=None):
        self.base_url = (base_url or os.getenv("QWEN_BASE_URL", "http://127.0.0.1:8080")).rstrip(
            "/"
        )
        parsed = urlparse(self.base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/v1"}
        ):
            raise ValueError("QWEN_BASE_URL must be a local HTTP address, optionally ending in /v1")
        if self.base_url.endswith("/v1"):
            self.base_url = self.base_url[:-3]
        self.model = model or os.getenv("QWEN_MODEL_ALIAS", "qwen-cleaner")
        self.transport = transport
        self._client = httpx.Client(
            timeout=300, trust_env=False, follow_redirects=False, transport=self.transport
        )
        self._cache = {}
        self.metrics = {"requests": 0, "cache_hits": 0, "request_seconds": 0.0}

    def analyze(self, role: str, payload: dict | list, response_type: type[BaseModel]):
        encoded_payload = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        cache_key = (role, encoded_payload, response_type.__name__)
        if cache_key in self._cache:
            self.metrics["cache_hits"] += 1
            return response_type.model_validate(self._cache[cache_key].model_dump())
        token_limits = {"schema": 4096, "categories": 3072, "adaptive": 2048}
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": load_prompt(role)},
                {
                    "role": "user",
                    "content": encoded_payload,
                },
            ],
            "response_format": {"type": "json_object", "schema": response_type.model_json_schema()},
            "temperature": 0.0,
            "max_tokens": token_limits.get(role, 2048),
            "chat_template_kwargs": {"enable_thinking": False},
            "stream": False,
        }
        started = time.perf_counter()
        try:
            response = self._client.post(f"{self.base_url}/v1/chat/completions", json=body)
            response.raise_for_status()
            choice = response.json()["choices"][0]
            if choice["finish_reason"] != "stop":
                raise ModelError("Model output was incomplete; no changes were applied")
            parsed = response_type.model_validate_json(choice["message"]["content"])
            self._cache[cache_key] = parsed
            return parsed
        except httpx.HTTPError as exc:
            raise ModelError(
                "Local Qwen request failed. Check the server, model and context size."
            ) from exc
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ModelError(
                "Qwen returned invalid structured output; no changes were applied"
            ) from exc
        finally:
            self.metrics["requests"] += 1
            self.metrics["request_seconds"] += time.perf_counter() - started

    def close(self):
        self._client.close()
