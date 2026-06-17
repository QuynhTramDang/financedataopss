"""LLM providers + structured-output call.

Hai loại provider:
  - anthropic        : Claude (planner/reasoning/review/RCA/claim-split + small model)
  - openai_compat    : model nhỏ qua endpoint OpenAI-compatible (Qwen/Gemma: Ollama, OpenRouter, ...)

Triết lý (§26, FR-018): mọi LLM call yêu cầu structured output, validate schema, retry tối đa N
lần với hướng dẫn sửa; sau N lần vẫn sai → raise LLMSchemaError để node treat-as-fail (escalate),
KHÔNG bao giờ để output sai schema lọt vào downstream.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional


# ── Exceptions ───────────────────────────────────────────────
class ProviderError(Exception):
    """Provider gọi API lỗi (network/timeout/auth)."""


class ProviderUnavailable(ProviderError):
    """Provider không cấu hình được (thiếu key/SDK) → router sẽ fallback."""


class LLMSchemaError(Exception):
    """LLM trả output sai schema sau khi đã retry hết số lần cho phép."""


# ── Response ─────────────────────────────────────────────────
@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0


# ── Base ─────────────────────────────────────────────────────
class BaseProvider:
    name: str
    model: str

    def complete(self, prompt: str, system: Optional[str] = None,
                 temperature: float = 0.0, max_tokens: int = 2048) -> LLMResponse:
        raise NotImplementedError


# ── Anthropic (Claude) ───────────────────────────────────────
class AnthropicProvider(BaseProvider):
    def __init__(self, name: str, model: str, api_key: Optional[str] = None):
        self.name = name
        self.model = model
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ProviderUnavailable("ANTHROPIC_API_KEY chưa được set")
        try:
            import anthropic  # noqa: WPS433  (lazy import)
        except ImportError as exc:  # pragma: no cover
            raise ProviderUnavailable("Chưa cài package `anthropic`") from exc
        self._client = anthropic.Anthropic(api_key=self._api_key)

    def complete(self, prompt, system=None, temperature=0.0, max_tokens=2048) -> LLMResponse:
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # broad: SDK ném nhiều loại lỗi
            raise ProviderError(f"Anthropic call lỗi: {exc}") from exc
        text = "".join(getattr(block, "text", "") for block in resp.content)
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=text,
            model=self.model,
            provider=self.name,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )


# ── OpenAI-compatible (Qwen/Gemma local hoặc hosted) ─────────
class OpenAICompatProvider(BaseProvider):
    def __init__(self, name: str, model: str, base_url: str, api_key: str):
        self.name = name
        self.model = model
        if not base_url or not model:
            raise ProviderUnavailable("SMALL_MODEL_BASE_URL/NAME chưa cấu hình")
        try:
            from openai import OpenAI  # noqa: WPS433
        except ImportError as exc:  # pragma: no cover
            raise ProviderUnavailable("Chưa cài package `openai`") from exc
        # nhiều endpoint local không yêu cầu key thật nhưng SDK cần một giá trị
        self._client = OpenAI(base_url=base_url, api_key=api_key or "not-needed")

    def complete(self, prompt, system=None, temperature=0.0, max_tokens=2048) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise ProviderError(f"OpenAI-compat call lỗi: {exc}") from exc
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=text,
            model=self.model,
            provider=self.name,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )


# ── Factory ──────────────────────────────────────────────────
def build_provider(name: str, cfg: dict) -> BaseProvider:
    """Tạo provider từ block config trong models.yaml. Có thể ném ProviderUnavailable."""
    ptype = cfg.get("type")
    if ptype == "anthropic":
        model = os.getenv(cfg.get("model_env", ""), "") or cfg.get("model_default", "")
        return AnthropicProvider(name=name, model=model)
    if ptype == "openai_compat":
        return OpenAICompatProvider(
            name=name,
            model=os.getenv(cfg.get("model_env", ""), ""),
            base_url=os.getenv(cfg.get("base_url_env", ""), ""),
            api_key=os.getenv(cfg.get("api_key_env", ""), ""),
        )
    raise ProviderUnavailable(f"Loại provider không hỗ trợ: {ptype}")


# ── JSON extraction helper ───────────────────────────────────
_JSON_BLOCK = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


def extract_json(text: str) -> Any:
    """Lấy JSON từ text LLM (chịu được ```json fences và prose xung quanh)."""
    cleaned = text.strip()
    # bỏ code fence nếu có
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(cleaned)
        if not match:
            raise
        return json.loads(match.group(0))
