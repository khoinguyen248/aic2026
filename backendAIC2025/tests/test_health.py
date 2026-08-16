from app import create_app


def test_app_health():
    app = create_app()
    client = app.test_client()

    response = client.get("/health/app")
    body = response.get_json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["mongo_enabled"] is False
    assert body["search_enabled"] is False


def test_mongo_health_when_disabled():
    app = create_app()
    client = app.test_client()

    response = client.get("/health/db1")
    body = response.get_json()

    assert response.status_code == 503
    assert body["enabled"] is False