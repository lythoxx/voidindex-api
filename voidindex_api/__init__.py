from flask import Flask
from flask_cors import CORS

from voidindex_api.src.api import bp


def create_app(test_config=None):
    app = Flask(__name__)
    CORS(app)
    if test_config:
        app.config.update(test_config)

    app.config.from_mapping(
        DATABASE_DSN="host=127.0.0.1 dbname=voidindex user=voidindex password=password",
    )

    app.register_blueprint(bp)

    return app
