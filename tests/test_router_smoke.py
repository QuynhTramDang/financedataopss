"""Smoke test cho model router (Step 0).

Phần lớn test không cần API key — dùng FakeProvider để kiểm tra:
  - extract_json chịu được fence/prose
  - call_structured validate schema, retry khi sai, raise khi hết retry
  - resolve fallback khi provider chính không khả dụng

Có 1 test live (gọi Claude thật) — tự skip nếu thiếu ANTHROPIC_API_KEY.
"""

import os

import pytest

from model_router.providers import (
    LLMResponse,
    LLMSchemaError,
    ProviderUnavailable,
    extract_json,
)
from model_router.router import ModelRouter, get_router


# ── extract_json ─────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('Đây là kết quả:\n{"a": 1, "b": "x"}\nHết.', {"a": 1, "b": "x"}),
    ('[1, 2, 3]', [1, 2, 3]),
])
def test_extract_json(raw, expected):
    assert extract_json(raw) == expected


# ── FakeProvider để test call_structured không cần network ──
class FakeProvider:
    def __init__(self, scripted_texts):
        self.name = "fake"
        self.model = "fake-model"
        self._texts = list(scripted_texts)
        self.calls = 0

    def complete(self, prompt, system=None, temperature=0.0, max_tokens=2048):
        text = self._texts[min(self.calls, len(self._texts) - 1)]
        self.calls += 1
        return LLMResponse(text=text, model=self.model, provider=self.name)


SCHEMA = {
    "type": "object",
    "properties": {"intent": {"type": "string"}, "risk": {"type": "string"}},
    "required": ["intent", "risk"],
    "additionalProperties": False,
}


def _router():
    return ModelRouter()


def test_call_structured_success(monkeypatch):
    router = _router()
    fake = FakeProvider(['{"intent": "investigate", "risk": "high"}'])
    monkeypatch.setattr(router, "resolve", lambda route: fake)
    out = router.call_structured("classifier", "phân loại đi", SCHEMA)
    assert out == {"intent": "investigate", "risk": "high"}
    assert fake.calls == 1


def test_call_structured_retries_then_succeeds(monkeypatch):
    router = _router()
    fake = FakeProvider([
        'không phải json',                       # sai → retry
        '{"intent": "x"}',                       # thiếu field → retry
        '{"intent": "investigate", "risk": "low"}',  # ok
    ])
    monkeypatch.setattr(router, "resolve", lambda route: fake)
    out = router.call_structured("classifier", "p", SCHEMA, max_retries=2)
    assert out["risk"] == "low"
    assert fake.calls == 3


def test_call_structured_raises_after_retries(monkeypatch):
    router = _router()
    fake = FakeProvider(['vẫn sai', 'lại sai', 'sai nữa'])
    monkeypatch.setattr(router, "resolve", lambda route: fake)
    with pytest.raises(LLMSchemaError):
        router.call_structured("classifier", "p", SCHEMA, max_retries=2)


def test_resolve_unknown_route():
    router = _router()
    with pytest.raises(ValueError):
        router.resolve("khong_ton_tai")


def test_classifier_falls_back_when_small_model_unavailable(monkeypatch):
    """small_openai_compat không khả dụng → route classifier phải fallback sang anthropic_small.

    Test thứ tự fallback một cách deterministic, không phụ thuộc SDK đã cài hay chưa:
    giả lập build_provider raise cho small_openai_compat, thành công cho provider khác.
    """
    import model_router.router as router_mod

    def fake_build(name, cfg):
        if name == "small_openai_compat":
            raise ProviderUnavailable("giả lập: chưa cấu hình endpoint")
        return _named_provider(name)

    monkeypatch.setattr(router_mod, "build_provider", fake_build)
    router = ModelRouter()
    provider = router.resolve("classifier")
    assert provider.name == "anthropic_small"


def _named_provider(name):
    p = FakeProvider(["{}"])
    p.name = name
    return p


# ── Live test (skip nếu không có key) ────────────────────────
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="cần ANTHROPIC_API_KEY")
def test_live_claude_structured():
    router = get_router()
    out = router.call_structured(
        route="planner",
        prompt="Trả về intent='ping' và risk='low'.",
        schema=SCHEMA,
    )
    assert set(out.keys()) >= {"intent", "risk"}
