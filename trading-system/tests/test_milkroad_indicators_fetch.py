import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "feeds"))

from fetch_milkroad_indicators import get_path  # noqa: E402


def test_get_path_simple_dict():
    assert get_path({"data": {"score": 62}}, "data.score") == 62


def test_get_path_with_label():
    body = {"data": {"score": 71, "label": "Greed"}}
    assert get_path(body, "data.score") == 71
    assert get_path(body, "data.label") == "Greed"


def test_get_path_through_list_index():
    body = {"items": [{"value": 10}, {"value": 20}]}
    assert get_path(body, "items.1.value") == 20


def test_get_path_missing_key_returns_none():
    assert get_path({"data": {"score": 1}}, "data.missing") is None


def test_get_path_missing_intermediate_returns_none():
    assert get_path({"data": {}}, "data.nested.score") is None


def test_get_path_wrong_type_returns_none_not_crash():
    # "score" is a number, not a dict/list -- can't descend further.
    assert get_path({"data": {"score": 5}}, "data.score.deeper") is None


def test_get_path_list_index_out_of_range_returns_none():
    assert get_path({"items": [1, 2]}, "items.5") is None


def test_get_path_list_non_numeric_segment_returns_none():
    assert get_path({"items": [1, 2]}, "items.notanumber") is None
