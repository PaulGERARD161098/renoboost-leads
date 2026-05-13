"""Tests du cache L4 (hash + persistance SQLite)."""

from __future__ import annotations

from renoboost_leads.stage4_prospection.cache import CacheStage4, calcul_cache_key


class TestCalculCacheKey:
    def test_meme_input_meme_hash(self):
        k1 = calcul_cache_key("v1", "claude-haiku-4-5", "ctx", True)
        k2 = calcul_cache_key("v1", "claude-haiku-4-5", "ctx", True)
        assert k1 == k2

    def test_prompt_version_change_invalide(self):
        k1 = calcul_cache_key("v1", "claude-haiku-4-5", "ctx", True)
        k2 = calcul_cache_key("v2", "claude-haiku-4-5", "ctx", True)
        assert k1 != k2

    def test_modele_change_invalide(self):
        k1 = calcul_cache_key("v1", "claude-haiku-4-5", "ctx", True)
        k2 = calcul_cache_key("v1", "claude-sonnet-4-6", "ctx", True)
        assert k1 != k2

    def test_contexte_change_invalide(self):
        k1 = calcul_cache_key("v1", "claude-haiku-4-5", "ctx-A", True)
        k2 = calcul_cache_key("v1", "claude-haiku-4-5", "ctx-B", True)
        assert k1 != k2

    def test_inclure_pitch_change_invalide(self):
        k1 = calcul_cache_key("v1", "claude-haiku-4-5", "ctx", True)
        k2 = calcul_cache_key("v1", "claude-haiku-4-5", "ctx", False)
        assert k1 != k2

    def test_hash_court_lisible(self):
        k = calcul_cache_key("v1", "claude-haiku-4-5", "ctx", True)
        assert len(k) == 16
        assert all(c in "0123456789abcdef" for c in k)


class TestCacheStage4:
    def test_get_inexistant_renvoie_none(self, tmp_path):
        cache = CacheStage4(tmp_path / "c.sqlite")
        assert cache.get("ChIJ_x", "k1") is None

    def test_store_then_get(self, tmp_path):
        cache = CacheStage4(tmp_path / "c.sqlite")
        cache.store("ChIJ_x", "k1", {"score_interet": 80, "raison_score": "ok"})
        got = cache.get("ChIJ_x", "k1")
        assert got == {"score_interet": 80, "raison_score": "ok"}

    def test_cache_key_different_meme_place_pas_de_collision(self, tmp_path):
        cache = CacheStage4(tmp_path / "c.sqlite")
        cache.store("ChIJ_x", "k1", {"score_interet": 80})
        cache.store("ChIJ_x", "k2", {"score_interet": 50})
        assert cache.get("ChIJ_x", "k1") == {"score_interet": 80}
        assert cache.get("ChIJ_x", "k2") == {"score_interet": 50}

    def test_count(self, tmp_path):
        cache = CacheStage4(tmp_path / "c.sqlite")
        assert cache.count() == 0
        cache.store("A", "k1", {"s": 1})
        cache.store("B", "k1", {"s": 2})
        cache.store("C", "k2", {"s": 3})
        assert cache.count() == 3
        assert cache.count("k1") == 2
        assert cache.count("k2") == 1

    def test_store_idempotent(self, tmp_path):
        cache = CacheStage4(tmp_path / "c.sqlite")
        cache.store("ChIJ_x", "k1", {"score_interet": 80})
        cache.store("ChIJ_x", "k1", {"score_interet": 90})  # overwrite
        assert cache.get("ChIJ_x", "k1") == {"score_interet": 90}
        assert cache.count() == 1
