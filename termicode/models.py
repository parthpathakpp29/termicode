from typing import List, Optional, Set

from termicode import catalog


def get_token_usage(tokens: int, model: str) -> tuple:
    """Returns (tokens_used, estimated_cost), priced from the live catalog.

    Falls back to a conservative non-zero estimate (matching this function's
    long-standing default) only when the model cannot be found in the catalog
    at all -- e.g. a manually typed id that does not exist, or the catalog is
    running on its last-resort fallback. Reporting $0 for an unknown model
    would repeat the exact mislabeling bug this whole module exists to fix.
    """
    price = catalog.price_lookup(model)
    if price is None:
        price = 0.50
    estimated_cost = (tokens / 1_000_000) * price
    return tokens, estimated_cost


def next_fallback_model(tried: Set[str], candidates: List[str]) -> Optional[str]:
    """The next untried model from an already-ranked candidate list.

    Candidates come pre-filtered and pre-ranked (best first) from
    catalog.free_coding_candidate_ids() or catalog.budget_candidate_ids() --
    this function's only job is "don't repeat one already tried." Returns
    None once every candidate has been tried, which is what bounds a fallback
    chain: exactly as long as the candidate list, no fixed attempt count.
    """
    for candidate in candidates:
        if candidate not in tried:
            return candidate
    return None


def route_model(user_prompt: str, current_model: str, candidates: List[str], user_manually_selected: bool, context_length: int = 0) -> str:
    """Choose a model for this turn.

    A manual override (via /model <name>) always wins. Otherwise, today's
    only policy is "take the best-ranked live candidate" -- there is no
    longer a reliable per-request signal (task complexity, model size) to
    route on beyond the catalog's own quality ranking, so every intent maps
    to the same top pick.

    user_prompt and context_length are accepted, not just current_model and
    candidates, so a future policy that does differentiate by task or
    conversation length can be added here without changing every call site
    again -- this function is the seam for that, even though today's policy
    does not use them.
    """
    if user_manually_selected or not candidates:
        return current_model
    return candidates[0]
