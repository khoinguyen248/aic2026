import pytest

from app.controllers.mongo_search_controller import _fuzzy_options, _integer_option


def test_integer_option_uses_default_and_bounds():
    assert _integer_option({}, "limit", 20, 1, 1000) == 20
    assert _integer_option({"limit": 0}, "limit", 20, 1, 1000) == 1
    assert _integer_option({"limit": 5000}, "limit", 20, 1, 1000) == 1000


def test_integer_option_rejects_invalid_value():
    with pytest.raises(ValueError, match="limit must be an integer"):
        _integer_option({"limit": "invalid"}, "limit", 20, 1, 1000)


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (-1, (None, 0)),
        (1, (1, 1)),
        (2, (2, 1)),
        (3, (2, 0)),
    ],
)
def test_fuzzy_level_mapping(level, expected):
    assert _fuzzy_options({"fuzzy_level": level}) == expected


def test_unknown_fuzzy_level_is_rejected():
    with pytest.raises(ValueError, match="fuzzy_level must be one of"):
        _fuzzy_options({"fuzzy_level": 4})
