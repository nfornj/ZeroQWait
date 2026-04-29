import numpy as np

from agent.cache import SemanticCache


class FakeEmbedder:
    def encode(self, texts):
        encoded = []
        for text in texts:
            if text == "test query":
                encoded.append(np.array([1.0, 0.0], dtype=float))
            elif text == "different query":
                encoded.append(np.array([0.0, 1.0], dtype=float))
            else:
                encoded.append(np.array([0.5, 0.5], dtype=float))
        return np.array(encoded)


def test_semantic_cache_round_trip(monkeypatch):
    cache = SemanticCache(threshold=0.92)
    monkeypatch.setattr("agent.cache.get_embedder", lambda: FakeEmbedder())

    payload = {"intent": "SEARCH", "search_terms": "barber"}
    cache.set("test query", payload)

    assert len(cache.local_cache) == 1
    assert cache.get("test query") == payload


def test_semantic_cache_miss_for_different_query(monkeypatch):
    cache = SemanticCache(threshold=0.92)
    monkeypatch.setattr("agent.cache.get_embedder", lambda: FakeEmbedder())

    payload = {"intent": "SEARCH", "search_terms": "barber"}
    cache.set("test query", payload)

    assert cache.get("different query") is None


def test_semantic_cache_no_embedder_is_safe(monkeypatch):
    cache = SemanticCache(threshold=0.92)
    monkeypatch.setattr("agent.cache.get_embedder", lambda: None)

    cache.set("test query", {"intent": "SEARCH"})

    assert cache.get("test query") is None
    assert cache.local_cache == []