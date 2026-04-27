from types import SimpleNamespace

from agents import llm_factory


class _FakeQuery:
    def __init__(self, record):
        self._record = record

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._record


class _FakeSession:
    def __init__(self, record):
        self._record = record

    def query(self, *_args, **_kwargs):
        return _FakeQuery(self._record)

    def close(self):
        return None


def test_provider_catalog_hides_groq_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_GROQ_PROVIDER", raising=False)

    providers = {provider["key"] for provider in llm_factory.provider_catalog("premium")}

    assert "groq" not in providers
    assert "ollama" in providers


def test_load_shop_llm_config_falls_back_when_groq_is_disabled(monkeypatch):
    groq_record = SimpleNamespace(
        provider="groq",
        model_name="llama-3.3-70b-versatile",
        api_base_url=None,
        api_key_encrypted=None,
        settings={"temperature": 0.2},
    )

    monkeypatch.delenv("ENABLE_GROQ_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setattr(llm_factory, "SessionLocal", lambda: _FakeSession(groq_record))
    monkeypatch.setattr(llm_factory, "_shop_subscription_tier", lambda _db, _shop_id: "premium")

    config = llm_factory.load_shop_llm_config(41)

    assert config.provider == "ollama"
    assert config.model_name == llm_factory.default_model_name_for_provider("ollama")
    assert config.settings == {}


def test_load_shop_llm_config_allows_groq_when_enabled(monkeypatch):
    groq_record = SimpleNamespace(
        provider="groq",
        model_name="llama-3.3-70b-versatile",
        api_base_url=None,
        api_key_encrypted=None,
        settings={"temperature": 0.2},
    )

    monkeypatch.setenv("ENABLE_GROQ_PROVIDER", "true")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setattr(llm_factory, "SessionLocal", lambda: _FakeSession(groq_record))
    monkeypatch.setattr(llm_factory, "_shop_subscription_tier", lambda _db, _shop_id: "premium")

    config = llm_factory.load_shop_llm_config(41)

    assert config.provider == "groq"
    assert config.model_name == "llama-3.3-70b-versatile"
    assert config.settings == {"temperature": 0.2}