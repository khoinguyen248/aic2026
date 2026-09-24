from app import create_app
import json


def test_app_health():
    app = create_app()
    client = app.test_client()

    response = client.get("/health/app")
    body = response.get_json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["mongo_enabled"] is False
    assert body["mongo_search_enabled"] is False
    assert body["search_enabled"] is False


def test_mongo_health_when_disabled():
    app = create_app()
    client = app.test_client()

    response = client.get("/health/db1")
    body = response.get_json()

    assert response.status_code == 503
    assert body["enabled"] is False


def test_mongo_search_disabled_by_default():
    # Khi cả hai hệ search tắt thì không có route /search nào.
    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/search/asr" not in routes
    assert "/search/ocr" not in routes
    assert "/search/collection" not in routes


def test_mongo_routes_do_not_require_qdrant(monkeypatch):
    monkeypatch.setattr("app.Config.MONGO_SEARCH_ENABLED", True)
    monkeypatch.setattr("app.Config.SEARCH_ENABLED", False)

    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/search/asr" in routes
    assert "/search/ocr" in routes
    assert "/search/collection" not in routes


def test_temporal_frames_uses_video_order(tmp_path):
    metadata_dir = tmp_path / "ocr"
    metadata_dir.mkdir()
    (metadata_dir / "L21_V001.json").write_text(
        json.dumps(
            [
                {"idx": 100, "keyframe_order": 0},
                {"idx": 500, "keyframe_order": 1},
                {"idx": 900, "keyframe_order": 2},
            ]
        ),
        encoding="utf-8",
    )
    app = create_app()
    app.config["METADATA_ROOT"] = str(tmp_path)

    response = app.test_client().post(
        "/search/infoframes", json={"L": "21", "V": "001", "idx": 500, "window": 1}
    )

    assert response.status_code == 200
    assert [item["idx"] for item in response.get_json()["results"]] == [100, 500, 900]
