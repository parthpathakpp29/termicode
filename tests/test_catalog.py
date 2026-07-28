import json
import time
import urllib.error

import pytest

from termicode import catalog


# Fixture models mirror the real OpenRouter API shapes verified during this
# project's own research (string per-token pricing, supported_parameters
# lists, nested artificial_analysis benchmarks) rather than an invented shape.
FREE_CODING_MODEL = {
    "id": "cohere/north-mini-code:free",
    "context_length": 256_000,
    "pricing": {"prompt": "0", "completion": "0"},
    "supported_parameters": ["tools", "tool_choice", "temperature"],
    "benchmarks": {"artificial_analysis": {"coding_index": 36.5, "intelligence_index": 19.8}},
}
FREE_BETTER_CODING_MODEL = {
    "id": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "context_length": 1_000_000,
    "pricing": {"prompt": "0", "completion": "0"},
    "supported_parameters": ["tools", "tool_choice"],
    "benchmarks": {"artificial_analysis": {"coding_index": 49.3}},
}
FREE_NO_TOOLS_MODEL = {
    "id": "some/free-chat-only",
    "context_length": 128_000,
    "pricing": {"prompt": "0", "completion": "0"},
    "supported_parameters": ["temperature"],
}
FREE_TINY_CONTEXT_MODEL = {
    "id": "some/free-tiny-context",
    "context_length": 8_000,
    "pricing": {"prompt": "0", "completion": "0"},
    "supported_parameters": ["tools", "tool_choice"],
}
PAID_MISLABELED_MODEL = {
    # Mirrors the real bug this module exists to prevent: same family name,
    # non-free variant, must never satisfy is_free().
    "id": "nvidia/nemotron-3-ultra-550b-a55b",
    "context_length": 512_288,
    "pricing": {"prompt": "0.0000005", "completion": "0.0000022"},
    "supported_parameters": ["tools", "tool_choice"],
}
CHEAP_BUDGET_MODEL = {
    "id": "kwaipilot/kat-coder-pro-v2.5",
    "context_length": 256_000,
    "pricing": {"prompt": "0.00000074", "completion": "0.00000296"},
    "supported_parameters": ["tools", "tool_choice"],
    "benchmarks": {"artificial_analysis": {"coding_index": 40.0}},
}
CHEAPER_BUDGET_MODEL = {
    "id": "openai/gpt-5.6-luna",
    "context_length": 1_050_000,
    "pricing": {"prompt": "0.0000005", "completion": "0.000003"},
    "supported_parameters": ["tools", "tool_choice"],
    "benchmarks": {"artificial_analysis": {"coding_index": 55.0}},
}
EXPENSIVE_PREMIUM_MODEL = {
    "id": "anthropic/claude-opus-4-8",
    "context_length": 400_000,
    "pricing": {"prompt": "0.000005", "completion": "0.000025"},
    "supported_parameters": ["tools", "tool_choice"],
    "benchmarks": {"artificial_analysis": {"coding_index": 80.0}},
}
MALFORMED_PRICING_MODEL = {
    "id": "some/malformed-pricing",
    "context_length": 100_000,
    "pricing": {"prompt": None, "completion": "not-a-number"},
    "supported_parameters": ["tools", "tool_choice"],
}
NEGATIVE_SENTINEL_PRICING_MODEL = {
    # Mirrors a real entry found on the live OpenRouter API during this
    # module's own verification: "openrouter/auto" prices at "-2" per token
    # to mean "variable, pass-through pricing", not a real negative price.
    "id": "openrouter/auto",
    "context_length": 128_000,
    "pricing": {"prompt": "-2", "completion": "-2"},
    "supported_parameters": ["tools", "tool_choice"],
}

FULL_CATALOG = [
    FREE_CODING_MODEL,
    FREE_BETTER_CODING_MODEL,
    FREE_NO_TOOLS_MODEL,
    FREE_TINY_CONTEXT_MODEL,
    PAID_MISLABELED_MODEL,
    CHEAP_BUDGET_MODEL,
    CHEAPER_BUDGET_MODEL,
    EXPENSIVE_PREMIUM_MODEL,
    MALFORMED_PRICING_MODEL,
    NEGATIVE_SENTINEL_PRICING_MODEL,
]


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TERMICODE_HOME", str(home))
    return home


# --- is_free / supports_tools / combined_price_per_m / coding_score ---

def test_is_free_true_for_zero_pricing():
    assert catalog.is_free(FREE_CODING_MODEL) is True


def test_is_free_false_for_the_exact_mislabeling_bug_this_module_prevents():
    """The precise real bug found in the old static table: a paid sibling of
    a free model, sharing most of the name, must never read as free."""
    assert catalog.is_free(PAID_MISLABELED_MODEL) is False


def test_is_free_false_on_malformed_pricing_rather_than_raising():
    assert catalog.is_free(MALFORMED_PRICING_MODEL) is False


def test_supports_tools_requires_both_tools_and_tool_choice():
    assert catalog.supports_tools(FREE_CODING_MODEL) is True
    assert catalog.supports_tools(FREE_NO_TOOLS_MODEL) is False


def test_combined_price_per_m_converts_per_token_to_per_million():
    # 0.0000005 + 0.0000022 per token -> 2.7 per million
    assert catalog.combined_price_per_m(PAID_MISLABELED_MODEL) == pytest.approx(2.7)


def test_combined_price_per_m_is_infinite_on_malformed_pricing():
    assert catalog.combined_price_per_m(MALFORMED_PRICING_MODEL) == float("inf")


def test_negative_sentinel_pricing_is_never_free_and_never_budget_eligible():
    """Found via a real, live catalog fetch during this module's own
    verification: "openrouter/auto" prices at -2/token as a "variable
    pricing" sentinel. Without a guard it would rank as the single cheapest
    model in the entire catalog, ahead of every genuinely free one."""
    assert catalog.is_free(NEGATIVE_SENTINEL_PRICING_MODEL) is False
    assert catalog.combined_price_per_m(NEGATIVE_SENTINEL_PRICING_MODEL) == float("inf")

    ids_in_budget_tier = [m["id"] for m in catalog.budget_models(FULL_CATALOG)]
    assert NEGATIVE_SENTINEL_PRICING_MODEL["id"] not in ids_in_budget_tier


def test_coding_score_prefers_coding_index_over_intelligence_index():
    assert catalog.coding_score(FREE_CODING_MODEL) == 36.5


def test_coding_score_falls_back_to_zero_when_no_benchmarks_present():
    assert catalog.coding_score(FREE_NO_TOOLS_MODEL) == 0.0


# --- free_coding_models / budget_models ---

def test_free_coding_models_excludes_non_free_no_tools_and_tiny_context():
    result = catalog.free_coding_models(FULL_CATALOG)
    ids = [m["id"] for m in result]

    assert PAID_MISLABELED_MODEL["id"] not in ids
    assert FREE_NO_TOOLS_MODEL["id"] not in ids
    assert FREE_TINY_CONTEXT_MODEL["id"] not in ids


def test_free_coding_models_ranks_by_coding_score_best_first():
    result = catalog.free_coding_models(FULL_CATALOG)

    assert [m["id"] for m in result] == [
        FREE_BETTER_CODING_MODEL["id"],  # coding_index 49.3
        FREE_CODING_MODEL["id"],  # coding_index 36.5
    ]


def test_budget_models_excludes_free_and_over_ceiling_models():
    result = catalog.budget_models(FULL_CATALOG)
    ids = [m["id"] for m in result]

    assert FREE_CODING_MODEL["id"] not in ids
    assert EXPENSIVE_PREMIUM_MODEL["id"] not in ids  # combined ~30/M, over the 5.0 ceiling


def test_budget_models_ranks_cheapest_first():
    # PAID_MISLABELED_MODEL is a real, confirmed-price paid model too (2.7/M
    # combined) -- it belongs in this ranking; it is only excluded from
    # is_free(), not from the budget tier, which is exactly correct.
    result = catalog.budget_models(FULL_CATALOG)

    assert [m["id"] for m in result] == [
        PAID_MISLABELED_MODEL["id"],  # ~2.7/M
        CHEAPER_BUDGET_MODEL["id"],  # ~3.5/M
        CHEAP_BUDGET_MODEL["id"],  # ~3.7/M
    ]


def test_budget_models_respects_a_custom_ceiling():
    # Only PAID_MISLABELED_MODEL (~2.7/M) clears a 3.0 ceiling; the other two
    # paid fixtures (~3.5/M, ~3.7/M) do not.
    result = catalog.budget_models(FULL_CATALOG, max_combined=3.0)

    assert [m["id"] for m in result] == [PAID_MISLABELED_MODEL["id"]]


# --- caching and staleness ---

def test_get_catalog_returns_a_fresh_cache_without_fetching(isolated_home, monkeypatch):
    catalog.save_cached_catalog(FULL_CATALOG)

    def fail_if_called(timeout=catalog.FETCH_TIMEOUT_SECONDS):
        raise AssertionError("fetch_catalog should not be called for a fresh cache")

    monkeypatch.setattr(catalog, "fetch_catalog", fail_if_called)

    assert catalog.get_catalog() == FULL_CATALOG


def test_get_catalog_refetches_a_stale_cache(isolated_home, monkeypatch):
    catalog.save_cached_catalog([FREE_CODING_MODEL])
    stale_time = time.time() - catalog.CATALOG_TTL_SECONDS - 1
    cache_file = isolated_home / "catalog.json"
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    payload["fetched_at"] = stale_time
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(catalog, "fetch_catalog", lambda timeout=catalog.FETCH_TIMEOUT_SECONDS: FULL_CATALOG)

    assert catalog.get_catalog() == FULL_CATALOG


def test_get_catalog_force_refresh_ignores_a_fresh_cache(isolated_home, monkeypatch):
    catalog.save_cached_catalog([FREE_CODING_MODEL])
    monkeypatch.setattr(catalog, "fetch_catalog", lambda timeout=catalog.FETCH_TIMEOUT_SECONDS: FULL_CATALOG)

    assert catalog.get_catalog(force_refresh=True) == FULL_CATALOG


def test_get_catalog_serves_stale_cache_when_refetch_fails(isolated_home, monkeypatch, capsys):
    catalog.save_cached_catalog([FREE_CODING_MODEL])
    cache_file = isolated_home / "catalog.json"
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    payload["fetched_at"] = time.time() - catalog.CATALOG_TTL_SECONDS - 1
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    def raise_network_error(timeout=catalog.FETCH_TIMEOUT_SECONDS):
        raise urllib.error.URLError("network is down")

    monkeypatch.setattr(catalog, "fetch_catalog", raise_network_error)

    result = catalog.get_catalog()

    assert result == [FREE_CODING_MODEL]
    assert "last known list" in capsys.readouterr().out


def test_get_catalog_falls_back_to_last_resort_with_no_cache_and_failed_fetch(isolated_home, monkeypatch, capsys):
    def raise_network_error(timeout=catalog.FETCH_TIMEOUT_SECONDS):
        raise urllib.error.URLError("network is down")

    monkeypatch.setattr(catalog, "fetch_catalog", raise_network_error)

    result = catalog.get_catalog()

    assert result == catalog.LAST_RESORT_MODELS
    assert "built-in fallback" in capsys.readouterr().out


def test_get_catalog_saves_a_successful_fetch_to_cache(isolated_home, monkeypatch):
    monkeypatch.setattr(catalog, "fetch_catalog", lambda timeout=catalog.FETCH_TIMEOUT_SECONDS: FULL_CATALOG)

    catalog.get_catalog()

    cached = catalog.load_cached_catalog()
    assert cached is not None
    assert cached[0] == FULL_CATALOG


def test_load_cached_catalog_returns_none_on_corrupt_json(isolated_home):
    (isolated_home / "catalog.json").write_text("not valid json{{{", encoding="utf-8")

    assert catalog.load_cached_catalog() is None


def test_load_cached_catalog_returns_none_when_no_cache_exists(isolated_home):
    assert catalog.load_cached_catalog() is None


# --- convenience id-list helpers ---

def test_free_coding_candidate_ids_returns_ranked_ids(isolated_home, monkeypatch):
    monkeypatch.setattr(catalog, "fetch_catalog", lambda timeout=catalog.FETCH_TIMEOUT_SECONDS: FULL_CATALOG)

    assert catalog.free_coding_candidate_ids() == [
        FREE_BETTER_CODING_MODEL["id"],
        FREE_CODING_MODEL["id"],
    ]


def test_free_coding_candidate_ids_falls_back_to_last_resort_when_filter_matches_nothing(isolated_home, monkeypatch):
    catalog_with_no_qualifying_free_model = [FREE_NO_TOOLS_MODEL, PAID_MISLABELED_MODEL]
    monkeypatch.setattr(
        catalog, "fetch_catalog", lambda timeout=catalog.FETCH_TIMEOUT_SECONDS: catalog_with_no_qualifying_free_model
    )

    result = catalog.free_coding_candidate_ids()

    assert result == [m["id"] for m in catalog.LAST_RESORT_MODELS]


def test_budget_candidate_ids_returns_ranked_ids(isolated_home, monkeypatch):
    monkeypatch.setattr(catalog, "fetch_catalog", lambda timeout=catalog.FETCH_TIMEOUT_SECONDS: FULL_CATALOG)

    assert catalog.budget_candidate_ids() == [
        PAID_MISLABELED_MODEL["id"],
        CHEAPER_BUDGET_MODEL["id"],
        CHEAP_BUDGET_MODEL["id"],
    ]


def test_all_known_model_ids_includes_everything_regardless_of_price_or_tools(isolated_home, monkeypatch):
    monkeypatch.setattr(catalog, "fetch_catalog", lambda timeout=catalog.FETCH_TIMEOUT_SECONDS: FULL_CATALOG)

    ids = catalog.all_known_model_ids()

    assert PAID_MISLABELED_MODEL["id"] in ids
    assert FREE_NO_TOOLS_MODEL["id"] in ids
    assert len(ids) == len(FULL_CATALOG)


def test_price_lookup_returns_the_real_price_for_a_known_model(isolated_home, monkeypatch):
    monkeypatch.setattr(catalog, "fetch_catalog", lambda timeout=catalog.FETCH_TIMEOUT_SECONDS: FULL_CATALOG)

    assert catalog.price_lookup(PAID_MISLABELED_MODEL["id"]) == pytest.approx(2.7)
    assert catalog.price_lookup(FREE_CODING_MODEL["id"]) == 0.0


def test_price_lookup_returns_none_for_an_unknown_model(isolated_home, monkeypatch):
    monkeypatch.setattr(catalog, "fetch_catalog", lambda timeout=catalog.FETCH_TIMEOUT_SECONDS: FULL_CATALOG)

    assert catalog.price_lookup("nonexistent/model") is None


def test_ttl_is_configurable_via_environment_at_call_time(isolated_home, monkeypatch):
    """A real behavioral test, not just a check on the constant: a cache that
    is fresh under the default TTL must read as stale once the env override
    shrinks the TTL below the cache's actual age.
    """
    catalog.save_cached_catalog([FREE_CODING_MODEL])
    cache_file = isolated_home / "catalog.json"
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    payload["fetched_at"] = time.time() - 10  # 10 seconds old: fresh under the 6h default
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(catalog, "fetch_catalog", lambda timeout=catalog.FETCH_TIMEOUT_SECONDS: FULL_CATALOG)
    monkeypatch.setenv("TERMICODE_CATALOG_TTL_SECONDS", "1")  # shorter than the cache's real age

    assert catalog.get_catalog() == FULL_CATALOG  # treated as stale -> refetched
