"""The live OpenRouter model catalog: fetched, cached, filtered, and scored.

TermiCode used to hardcode a static table of "known free/premium models."
Cross-referencing that table against OpenRouter's real API during this
project's own research found most entries no longer existed at all, and one
of the survivors -- the tool's own hardcoded startup default -- was a paid
model silently mislabeled as free. Model catalogs on OpenRouter change fast
enough (ten new model families landed in three weeks during that research)
that any hand-maintained table will look like this again within months.

This module replaces the static table with a fetched, locally cached catalog,
plus pure filtering/scoring functions over it. Nothing here talks to a model
API for chat completions -- only to OpenRouter's public, unauthenticated
model-listing endpoint.
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

from termicode.session import termicode_home
from termicode.ui import print_warning


OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
FETCH_TIMEOUT_SECONDS = 10

# How long a cached catalog is trusted before a refresh is attempted.
# Deliberately short relative to how long a model release stays "new," but
# long enough that ordinary use across a single day of work never triggers a
# refetch. Overridable via $TERMICODE_CATALOG_TTL_SECONDS for testing or
# advanced use, matching the $TERMICODE_HOME override convention. The
# override is re-read at call time (see _catalog_ttl_seconds), not frozen at
# import, so it takes effect immediately rather than requiring a restart.
CATALOG_TTL_SECONDS = 6 * 60 * 60


def _catalog_ttl_seconds() -> int:
    return int(os.environ.get("TERMICODE_CATALOG_TTL_SECONDS", CATALOG_TTL_SECONDS))

MIN_CONTEXT_LENGTH = 32_000
BUDGET_MAX_COMBINED_PRICE_PER_M = 5.0

# Used only when there is no cache at all and a live fetch also fails (first
# run, offline). Both real, free, and tool-calling-capable as of this
# module's writing, verified directly against the OpenRouter API -- a safety
# net for the rare case where nothing else is available, not the design.
# Expect this to go stale eventually; that is acceptable precisely because it
# is never the primary path.
LAST_RESORT_MODELS = [
    {
        "id": "cohere/north-mini-code:free",
        "context_length": 256_000,
        "pricing": {"prompt": "0", "completion": "0"},
        "supported_parameters": ["tools", "tool_choice"],
        "benchmarks": {"artificial_analysis": {"coding_index": 36.5}},
    },
    {
        "id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "context_length": 1_000_000,
        "pricing": {"prompt": "0", "completion": "0"},
        "supported_parameters": ["tools", "tool_choice"],
        "benchmarks": {"artificial_analysis": {"coding_index": 49.3}},
    },
]

_FETCH_FAILURE_TYPES = (urllib.error.URLError, OSError, ValueError)


def _cache_path() -> Optional[Path]:
    home = termicode_home()
    return None if home is None else home / "catalog.json"


def fetch_catalog(timeout: int = FETCH_TIMEOUT_SECONDS) -> List[dict]:
    """Fetch the live catalog from OpenRouter. Raises on any failure.

    Uses the standard library rather than a new HTTP dependency: this is one
    unauthenticated GET, and the caching/fallback logic above it already
    supplies the retry/timeout handling a full HTTP client would otherwise
    provide.
    """
    request = urllib.request.Request(OPENROUTER_MODELS_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("data", [])


def load_cached_catalog() -> Optional[Tuple[List[dict], float]]:
    """Read the on-disk cache. None if missing, unreadable, or corrupt."""
    path = _cache_path()
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload["models"], payload["fetched_at"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_cached_catalog(models: List[dict]) -> None:
    path = _cache_path()
    if path is None:
        return
    try:
        path.write_text(json.dumps({"fetched_at": time.time(), "models": models}), encoding="utf-8")
    except OSError as exc:
        print_warning(f"Could not save the model catalog cache: {exc}")


def get_catalog(force_refresh: bool = False) -> List[dict]:
    """The live model catalog: cache-first, refreshed when stale.

    Degrades in three steps rather than failing outright: a fresh-enough
    cache is returned with no network call; a fetch failure with an existing
    cache serves that cache (stale but real beats hardcoded and dead); a
    fetch failure with no cache at all falls back to LAST_RESORT_MODELS.
    """
    cached = load_cached_catalog()
    if cached is not None and not force_refresh:
        models, fetched_at = cached
        if time.time() - fetched_at < _catalog_ttl_seconds():
            return models

    try:
        models = fetch_catalog()
        save_cached_catalog(models)
        return models
    except _FETCH_FAILURE_TYPES as exc:
        if cached is not None:
            print_warning(f"Could not refresh the model catalog ({exc}); using the last known list.")
            return cached[0]
        print_warning(f"Could not fetch the model catalog ({exc}); using a small built-in fallback list.")
        return LAST_RESORT_MODELS


def is_free(model: dict) -> bool:
    pricing = model.get("pricing") or {}
    try:
        return float(pricing.get("prompt", 1)) == 0.0 and float(pricing.get("completion", 1)) == 0.0
    except (TypeError, ValueError):
        return False


def supports_tools(model: dict) -> bool:
    supported = model.get("supported_parameters") or []
    return "tools" in supported and "tool_choice" in supported


def combined_price_per_m(model: dict) -> float:
    """Combined prompt+completion price per million tokens.

    Pricing in the API is per-token, as strings. Unparseable or negative
    pricing sorts to infinity rather than raising or looking "free": entries
    like "openrouter/auto" use a negative sentinel to mean variable,
    pass-through pricing rather than a real fixed price, and would otherwise
    look like the cheapest model in the entire catalog -- confirmed against
    the real live API, not a hypothetical.
    """
    pricing = model.get("pricing") or {}
    try:
        prompt = float(pricing.get("prompt", 0))
        completion = float(pricing.get("completion", 0))
    except (TypeError, ValueError):
        return float("inf")
    if prompt < 0 or completion < 0:
        return float("inf")
    return (prompt + completion) * 1_000_000


def coding_score(model: dict) -> float:
    """coding_index if present, else intelligence_index, else 0.0."""
    benchmarks = ((model.get("benchmarks") or {}).get("artificial_analysis")) or {}
    if benchmarks.get("coding_index") is not None:
        return float(benchmarks["coding_index"])
    if benchmarks.get("intelligence_index") is not None:
        return float(benchmarks["intelligence_index"])
    return 0.0


def context_length(model: dict) -> int:
    return model.get("context_length") or 0


def free_coding_models(catalog: List[dict]) -> List[dict]:
    """Free, tool-calling-capable models with enough context, best first.

    Ranked by coding_score, tie-broken by larger context_length. This
    replaces the static table's hand-assigned "free_coding" tier with a live
    quality signal.
    """
    candidates = [
        m for m in catalog
        if is_free(m) and supports_tools(m) and context_length(m) >= MIN_CONTEXT_LENGTH
    ]
    return sorted(candidates, key=lambda m: (coding_score(m), context_length(m)), reverse=True)


def budget_models(catalog: List[dict], max_combined: float = BUDGET_MAX_COMBINED_PRICE_PER_M) -> List[dict]:
    """Paid, tool-calling-capable models under a combined price ceiling.

    Cheapest first, tie-broken by higher coding_score. A price ceiling
    instead of a curated model list, for the same reason as free_coding_models:
    a hardcoded id list would rot the same way the old static table did.
    """
    candidates = [
        m for m in catalog
        if not is_free(m) and supports_tools(m) and combined_price_per_m(m) <= max_combined
    ]
    return sorted(candidates, key=lambda m: (combined_price_per_m(m), -coding_score(m)))


def free_coding_candidate_ids(force_refresh: bool = False) -> List[str]:
    """Ranked free-tier candidate ids, ready for route_model/next_fallback_model.

    Falls back to LAST_RESORT_MODELS if the live catalog, even after fetching,
    yields no qualifying candidate (e.g. a filter this strict happens to match
    nothing on a given day) -- so callers always get at least the safety net,
    never an empty list.
    """
    models = free_coding_models(get_catalog(force_refresh=force_refresh))
    if not models:
        models = LAST_RESORT_MODELS
    return [m["id"] for m in models]


def budget_candidate_ids(force_refresh: bool = False) -> List[str]:
    """Ranked budget-tier candidate ids (cheapest qualifying paid model first)."""
    models = budget_models(get_catalog(force_refresh=force_refresh))
    return [m["id"] for m in models]


def all_known_model_ids(force_refresh: bool = False) -> set:
    """Every model id currently on OpenRouter, for validating a manual /model pick."""
    return {m["id"] for m in get_catalog(force_refresh=force_refresh) if "id" in m}


def price_lookup(model_id: str, force_refresh: bool = False) -> Optional[float]:
    """Real combined price per million tokens for a specific model id, or
    None if it is not in the current catalog (e.g. a manually typed id that
    does not exist, or the catalog is on the stale/last-resort fallback)."""
    for model in get_catalog(force_refresh=force_refresh):
        if model.get("id") == model_id:
            return combined_price_per_m(model)
    return None
