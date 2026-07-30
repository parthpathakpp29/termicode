from termicode.ui import print_api_error


class _FakeRateLimitError(Exception):
    """A string shape matching what openai.RateLimitError actually stringifies
    to: "<n> <reason> - {<python-dict-literal>}"."""

    def __init__(self, message):
        super().__init__(message)
        self._message = message

    def __str__(self):
        return self._message


def test_print_api_error_extracts_the_clean_message_from_a_429(capsys):
    err = _FakeRateLimitError(
        "429 Rate limit reached - {'error': {'message': 'You are being rate limited.'}}"
    )

    print_api_error(err)
    rendered = capsys.readouterr().out

    assert "Rate Limit Exceeded" in rendered
    assert "You are being rate limited." in rendered


def test_print_api_error_falls_back_to_the_raw_string_on_malformed_429_body(capsys):
    """A 429-shaped message whose body isn't a parseable dict literal must
    not crash -- it should fall through to the plain error panel instead."""
    err = _FakeRateLimitError("429 Rate limit reached - not a valid dict at all")

    print_api_error(err)
    rendered = capsys.readouterr().out

    assert "API Error" in rendered


def test_print_api_error_renders_a_plain_error_for_non_rate_limit_errors(capsys):
    err = ConnectionError("network is unreachable")

    print_api_error(err)
    rendered = capsys.readouterr().out

    assert "API Error" in rendered
    assert "network is unreachable" in rendered


def test_print_api_error_does_not_treat_an_unrelated_429_substring_as_a_rate_limit(capsys):
    """The 429 branch requires both "429" and the literal phrase "Rate limit
    reached" -- an error that merely contains the number 429 incidentally
    must render as a plain error, not attempt the dict-literal parse."""
    err = ConnectionError("connection refused on port 42900")

    print_api_error(err)
    rendered = capsys.readouterr().out

    assert "API Error" in rendered
    assert "Rate Limit Exceeded" not in rendered
