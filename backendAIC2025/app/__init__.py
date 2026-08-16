from flask import Flask, jsonify
from flask_cors import CORS

from .config import Config
from .extensions import mongo, mongo2


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(
        app,
        resources={r"/*": {"origins": "*"}},
        supports_credentials=True,
    )

    if Config.MONGO_ENABLED:
        if not Config.MONGO_URI or not Config.MONGO_URI2:
            raise RuntimeError(
                "MONGO_ENABLED=true nhưng MONGO_URI hoặc MONGO_URI2 chưa được cấu hình"
            )

        mongo.init_app(app)
        mongo2.init_app(app, uri=Config.MONGO_URI2)

    @app.get("/health/app")
    def health_app():
        return jsonify(
            {
                "ok": True,
                "environment": Config.APP_ENV,
                "mongo_enabled": Config.MONGO_ENABLED,
                "search_enabled": Config.SEARCH_ENABLED,
            }
        ), 200

    @app.get("/health/db1")
    def health_db1():
        if not Config.MONGO_ENABLED:
            return jsonify(
                {
                    "ok": False,
                    "enabled": False,
                    "message": "MongoDB is disabled",
                }
            ), 503

        try:
            mongo.db.command("ping")
            return jsonify({"ok": True, "db": "MONGO_URI"}), 200
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.get("/health/db2")
    def health_db2():
        if not Config.MONGO_ENABLED:
            return jsonify(
                {
                    "ok": False,
                    "enabled": False,
                    "message": "MongoDB is disabled",
                }
            ), 503

        try:
            mongo2.db.command("ping")
            return jsonify({"ok": True, "db": "MONGO_URI2"}), 200
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    if Config.MONGO_ENABLED and Config.USER_ROUTES_ENABLED:
        from .routes.user_routes import user_bp

        app.register_blueprint(user_bp, url_prefix="/user")

    if Config.SEARCH_ENABLED:
        from .routes.search_routes import search_bp

        app.register_blueprint(search_bp, url_prefix="/search")

    return app