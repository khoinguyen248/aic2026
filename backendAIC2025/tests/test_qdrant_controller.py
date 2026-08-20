import pytest

from app.controllers.qdrant_controller import (
    _model_from_request,
    _top_k_from_request,
)


@pytest.mark.parametrize("model", ["beit3", "jina", "pe"])
def test_model_selection(model):
    assert _model_from_request(model) == model


def test_legacy_clip_name_maps_to_pe():
    assert _model_from_request("clip") == "pe"


def test_unknown_model_is_rejected():
    with pytest.raises(ValueError, match="model must be one of"):
        _model_from_request("unknown")


def test_top_k_is_bounded():
    assert _top_k_from_request({"top_k": 0}) == 1
    assert _top_k_from_request({"top_k": 5000}) == 1000
