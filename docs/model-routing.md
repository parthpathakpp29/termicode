# Model routing

TermiCode picks which model to use per turn from a live, fetched, cached list of OpenRouter models — not from a hardcoded table. This document covers how that list is built, how a model is chosen from it, and what happens when a model is rate-limited mid-conversation.

Relevant modules: `catalog.py` (fetch, cache, filter, score) and `models.py` (routing policy, cost lookup, fallback selection). Neither talks to a chat-completions endpoint — both are pure data/policy layers that `cli.py` calls into.

## Why a live catalog, not a static table

An earlier version of TermiCode hardcoded a table of "known free/premium models" directly in `models.py`. Cross-referencing that table against OpenRouter's real API found most entries no longer existed as model ids at all, and the tool's own hardcoded startup default was a real but *paid* model, silently mislabeled as free — meaning real money could be spent while the tool reported $0 cost. OpenRouter's catalog changes fast enough (new model families landing in the space of weeks) that any hand-maintained table decays the same way within months. `catalog.py` exists to make that class of bug structurally impossible: pricing and capability are always read from the live source, never asserted by hand.

## The catalog: fetch, cache, degrade

`catalog.get_catalog()` is the single entry point everything else calls:

1. **Fresh cache present** (younger than `CATALOG_TTL_SECONDS`, default 6 hours, overridable via `$TERMICODE_CATALOG_TTL_SECONDS`) → returned with no network call.
2. **Cache missing or stale** → a live fetch is attempted (`fetch_catalog`, a single unauthenticated GET to `openrouter.ai/api/v1/models` using the standard library `urllib`, not a new HTTP dependency). Success re-caches to `~/.termicode/catalog.json` and returns the fresh data.
3. **Fetch fails, but a cache exists** (even a stale one) → the stale cache is served, with a warning. Stale-but-real beats a hardcoded table that's simply wrong.
4. **Fetch fails and there is no cache at all** (first run, offline) → falls back to `LAST_RESORT_MODELS`, a small, explicitly-named constant of two models verified real and tool-calling-capable at the time this module was written. This is a safety net, not a design — it is expected to eventually go stale, which is acceptable because it is never the primary path.

The cache lives under `~/.termicode/` (see [sessions.md](sessions.md) for the shared home-directory resolution TermiCode uses for all of its on-disk state), keyed by `$TERMICODE_HOME` the same way session storage is.

## Filtering and scoring

These run over the catalog's real fields — pricing, `supported_parameters`, and OpenRouter's own `benchmarks.artificial_analysis` block — rather than a hand-assigned label:

- **`is_free(model)`** — both prompt and completion price parse to exactly `0.0`. Guards against malformed pricing (returns `False`, not an exception) and against a real anomaly found in the live catalog: some meta/routing-alias models (`openrouter/auto`) use a *negative* sentinel price to mean "variable, pass-through pricing." Negative pricing is treated as unusable, not as "impossibly cheap" — without that guard, those aliases would rank as the cheapest models in the entire catalog.
- **`supports_tools(model)`** — both `"tools"` and `"tool_choice"` appear in the model's `supported_parameters`. This is a hard requirement for `free_coding_models`/`budget_models`: TermiCode is entirely tool-call-driven, so a model that can't reliably take tool calls isn't a candidate regardless of how cheap or capable it otherwise looks.
- **`coding_score(model)`** — reads `benchmarks.artificial_analysis.coding_index`, falling back to `intelligence_index`, then `0.0` if neither is present.
- **`combined_price_per_m(model)`** — prompt + completion price per million tokens, converted from the API's per-token string values. Unparseable or negative pricing sorts to infinity rather than raising or looking free.

`free_coding_models(catalog)` and `budget_models(catalog, max_combined=...)` apply these as filters and rank the result — best `coding_score` first for the free tier, cheapest first for budget. `free_coding_candidate_ids()` and `budget_candidate_ids()` are the convenience wrappers that return plain id lists (falling back to `LAST_RESORT_MODELS` if the live-filtered result is ever empty), which is what `cli.py` and `models.py` actually consume.

## The three tiers, as `/model` exposes them

- **Free (default)** — `/model auto` (or just never touching `/model`). Auto-routes to the top of `free_coding_candidate_ids()`.
- **Budget** — `/model budget`. Pins to the cheapest model in `budget_candidate_ids()` under `BUDGET_MAX_COMBINED_PRICE_PER_M` (default $5/M combined). This is a price *policy*, not a curated id list, for the same reason the free tier isn't a static table — a hardcoded "cheap models" list would rot exactly the same way.
- **Premium / manual** — `/model <name>`, validated against `catalog.all_known_model_ids()` (every model currently on OpenRouter, free or not). Manual selection disables auto-routing until `/model auto` is run again, and is never silently overridden — see the fallback behavior below.

## Routing policy (`models.py`)

`route_model(user_prompt, current_model, candidates, user_manually_selected, context_length)` is deliberately kept as a real function rather than an inline expression at its call site, even though its current policy is short: a manual override always wins; otherwise it returns the top of `candidates`. `user_prompt` and `context_length` are accepted but unused by today's policy — they exist so a future routing policy that does differentiate by task or conversation length can be added here without changing every call site. (An earlier design routed "coding" vs. "simple" questions to different model tiers by keyword; that distinction was removed because the live catalog provides a reliable quality signal but no reliable size/speed signal to route the two differently on.)

## Fallback on a rate limit

`cli._stream_with_fallback` wraps the streaming call. It catches `openai.RateLimitError` specifically — confirmed to be a real, structural exception (`status_code == 429`), not something to detect by string-matching an error message — and, only for auto-routed turns, retries with `models.next_fallback_model(tried, candidates)`: the next entry in the same ranked candidate list that hasn't been tried yet. The chain has no fixed length; it ends when every candidate has been tried, which bounds it naturally without a magic attempt count. A manually selected model is never substituted — a rate limit on an explicit choice surfaces exactly as it would without this mechanism.

The candidate list is fetched **once per turn** and reused for both the initial routing decision and the fallback chain, so they can never disagree about what the current live ranking is.

## Cost tracking

`get_token_usage(tokens, model)` prices from `catalog.price_lookup(model)` — the model's real, current combined price. If a model isn't found in the catalog at all (a manually typed id that doesn't exist, or the catalog running on its last-resort fallback), it falls back to a conservative non-zero estimate, never to `$0` — reporting `$0` for an unrecognized model is exactly how the original mislabeling bug happened.
