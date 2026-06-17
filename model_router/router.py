"""ModelRouter: resolve route → provider, structured-output call có retry + fallback.

Cách dùng:
    from model_router import get_router
    router = get_router()
    data = router.call_structured(
        route="classifier",
        prompt="...",
        schema={...},            # JSON Schema (dict)
        system="...",            # optional
    )

Hành vi:
  - provider của route không khả dụng (thiếu env) → dùng fallback_provider, rồi tới route mặc định.
  - LLM trả sai schema → retry tối đa `max_retries` lần kèm hướng dẫn sửa.
  - hết retry → raise LLMSchemaError (caller/node sẽ treat-as-fail và escalate).
  - mọi lần fallback/retry đều được log qua logger (Step 14 sẽ gắn observability đầy đủ).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml
from jsonschema import ValidationError, validate

from .providers import (
    BaseProvider,
    LLMSchemaError,
    ProviderError,
    ProviderUnavailable,
    build_provider,
    extract_json,
)

logger = logging.getLogger("model_router")

_DEFAULT_CFG_PATH = Path(__file__).with_name("models.yaml")


class ModelRouter:
    def __init__(self, config_path: Optional[str] = None):
        path = Path(config_path) if config_path else _DEFAULT_CFG_PATH
        with open(path, "r", encoding="utf-8") as fh:
            self._cfg = yaml.safe_load(fh)
        self._defaults = self._cfg.get("defaults", {})
        self._provider_cfgs = self._cfg.get("providers", {})
        self._routes = self._cfg.get("routes", {})
        self._provider_cache: dict[str, BaseProvider] = {}

    # ── provider resolution ──────────────────────────────────
    def _get_provider(self, provider_name: str) -> BaseProvider:
        """Trả provider đã khởi tạo; cache lại. Ném ProviderUnavailable nếu không dựng được."""
        if provider_name in self._provider_cache:
            return self._provider_cache[provider_name]
        cfg = self._provider_cfgs.get(provider_name)
        if not cfg:
            raise ProviderUnavailable(f"Provider '{provider_name}' không có trong config")
        provider = build_provider(provider_name, cfg)
        self._provider_cache[provider_name] = provider
        return provider

    def resolve(self, route: str) -> BaseProvider:
        """Resolve route → provider khả dụng, áp dụng chuỗi fallback."""
        route_cfg = self._routes.get(route)
        if not route_cfg:
            raise ValueError(f"Route '{route}' không tồn tại trong models.yaml")

        candidates = [route_cfg.get("provider")]
        if route_cfg.get("fallback_provider"):
            candidates.append(route_cfg["fallback_provider"])
        # fallback cuối cùng: provider của route mặc định
        fallback_route = self._defaults.get("fallback_route")
        if fallback_route and fallback_route in self._routes:
            candidates.append(self._routes[fallback_route].get("provider"))

        last_err: Optional[Exception] = None
        seen = set()
        for name in candidates:
            if not name or name in seen:
                continue
            seen.add(name)
            try:
                provider = self._get_provider(name)
                if name != route_cfg.get("provider"):
                    logger.warning("Route '%s' fallback sang provider '%s'", route, name)
                return provider
            except ProviderUnavailable as exc:
                last_err = exc
                logger.warning("Provider '%s' không khả dụng (%s), thử fallback", name, exc)
        raise ProviderUnavailable(
            f"Không provider nào khả dụng cho route '{route}': {last_err}"
        )

    # ── structured-output call ───────────────────────────────
    def call_structured(
        self,
        route: str,
        prompt: str,
        schema: dict,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        max_retries: Optional[int] = None,
    ) -> Any:
        """Gọi LLM, ép trả JSON đúng `schema`. Retry khi sai. Hết retry → LLMSchemaError."""
        retries = self._defaults.get("max_retries", 2) if max_retries is None else max_retries
        provider = self.resolve(route)

        sys_prompt = (system or "") + (
            "\n\nQUAN TRỌNG: Chỉ trả về MỘT object JSON hợp lệ, không kèm giải thích, "
            "không markdown fence. JSON phải khớp schema được yêu cầu."
        )
        schema_hint = f"\n\nJSON Schema bắt buộc:\n{_compact(schema)}"
        attempt_prompt = prompt + schema_hint

        last_error = ""
        for attempt in range(retries + 1):
            resp = provider.complete(
                prompt=attempt_prompt, system=sys_prompt,
                temperature=temperature, max_tokens=max_tokens,
            )
            try:
                data = extract_json(resp.text)
                validate(instance=data, schema=schema)
                logger.info(
                    "route=%s provider=%s model=%s tokens(in/out)=%d/%d attempt=%d",
                    route, resp.provider, resp.model,
                    resp.input_tokens, resp.output_tokens, attempt,
                )
                try:
                    from observability.trace_logger import record_llm
                    record_llm(route, resp.provider, resp.model,
                               resp.input_tokens, resp.output_tokens)
                except Exception:  # noqa: BLE001 — observability không bao giờ làm vỡ luồng chính
                    pass
                return data
            except (ValueError, ValidationError) as exc:
                last_error = str(exc)
                logger.warning("route=%s attempt=%d sai schema: %s", route, attempt, last_error)
                attempt_prompt = (
                    prompt + schema_hint
                    + f"\n\nLần trước output KHÔNG hợp lệ ({last_error}). "
                    + "Hãy sửa và chỉ trả về JSON đúng schema."
                )

        raise LLMSchemaError(
            f"Route '{route}' trả sai schema sau {retries + 1} lần. Lỗi cuối: {last_error}"
        )


def _compact(schema: dict) -> str:
    import json
    return json.dumps(schema, ensure_ascii=False, separators=(",", ":"))


# ── singleton ────────────────────────────────────────────────
_router_singleton: Optional[ModelRouter] = None


def get_router(config_path: Optional[str] = None) -> ModelRouter:
    global _router_singleton
    if _router_singleton is None or config_path is not None:
        # load .env nếu có (không bắt buộc)
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        _router_singleton = ModelRouter(config_path)
    return _router_singleton
