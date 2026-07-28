from termicode.models import get_token_usage


def test_get_token_usage_prices_from_the_live_catalog(monkeypatch):
    monkeypatch.setattr("termicode.models.catalog.price_lookup", lambda model: 2.0)

    tokens, cost = get_token_usage(1_000_000, "some/paid-model")

    assert tokens == 1_000_000
    assert cost == 2.0


def test_get_token_usage_is_zero_for_a_real_free_model(monkeypatch):
    """The exact property the old static table got backwards for its own
    hardcoded default: a genuinely free model must report $0, not a
    fallback estimate."""
    monkeypatch.setattr("termicode.models.catalog.price_lookup", lambda model: 0.0)

    _, cost = get_token_usage(500_000, "some/free-model")

    assert cost == 0.0


def test_get_token_usage_does_not_silently_report_zero_for_an_unknown_model(monkeypatch):
    """A model missing from the catalog entirely (e.g. a manually typed id
    that does not exist, or the catalog on its last-resort fallback) must not
    read as free -- that is precisely how the original bug happened."""
    monkeypatch.setattr("termicode.models.catalog.price_lookup", lambda model: None)

    _, cost = get_token_usage(1_000_000, "unknown/model")

    assert cost > 0.0


def test_get_token_usage_scales_with_token_count(monkeypatch):
    monkeypatch.setattr("termicode.models.catalog.price_lookup", lambda model: 4.0)

    _, cost_at_half_a_million = get_token_usage(500_000, "some/paid-model")
    _, cost_at_one_million = get_token_usage(1_000_000, "some/paid-model")

    assert cost_at_one_million == cost_at_half_a_million * 2
