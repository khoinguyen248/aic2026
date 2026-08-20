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


# NOTE: mongo_search_bp (ASR/OCR kiểu teammate) đã bị thay bằng ASR/OCR trong search_bp (code của bạn),
# đăng ký dưới SEARCH_ENABLED (kèm Qdrant). Test cũ kiểm tra mongo_search_bp không còn phù hợp.


def test_mongo_search_disabled_by_default():
    # Mặc định SEARCH_ENABLED=False -> không đăng ký route /search nào (kể cả của teammate lẫn của bạn)
    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/search/asr" not in routes
    assert "/search/ocr" not in routes
    assert "/search/collection" not in routes
