from app import create_app


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


def test_mongo_search_routes_are_registered_independently(monkeypatch):
    monkeypatch.setattr("app.Config.MONGO_SEARCH_ENABLED", True)
    monkeypatch.setattr("app.Config.SEARCH_ENABLED", False)

    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/search/ocr" in routes
    assert "/search/asr" in routes
    assert "/search/collection" not in routes
