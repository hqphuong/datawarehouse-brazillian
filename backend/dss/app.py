"""Application factory for the Flask DSS backend."""

from __future__ import annotations

from flask import Flask, Response, abort, request
from flask_cors import CORS
from werkzeug.exceptions import MethodNotAllowed

from .api import bp
from .config import load_config
from .json_provider import DssJSONProvider

DJANGO_404 = (
    "\n<!doctype html>\n<html lang=\"en\">\n<head>\n"
    "  <title>Not Found</title>\n</head>\n<body>\n"
    "  <h1>Not Found</h1><p>The requested resource was not found on this "
    "server.</p>\n</body>\n</html>\n"
)

DJANGO_500 = (
    "\n<!doctype html>\n<html lang=\"en\">\n<head>\n"
    "  <title>Server Error (500)</title>\n</head>\n<body>\n"
    "  <h1>Server Error (500)</h1>\n</body>\n</html>\n"
)

CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

# Methods advertised for each resource, matching Django's
# require_GET / require_http_methods decorators.
RESOURCE_METHODS = {
    "/api/dss/routes": ["GET"],
    "/api/dss/scenario": ["GET"],
    "/api/dss/promise": ["GET"],
    "/api/dss/actions": ["GET", "POST"],
    "/api/dss/brief": ["GET"],
    "/api/dss/attribution": ["GET"],
    "/api/dss/promise-policy": ["GET"],
    "/api/dss/sellers": ["GET"],
    "/api/dss/portfolio": ["GET"],
}


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(load_config())
    if test_config:
        app.config.update(test_config)

    app.json = DssJSONProvider(app)

    CORS(
        app,
        origins="*",
        send_wildcard=True,
        allow_headers=CORS_ALLOW_HEADERS,
        methods=CORS_ALLOW_METHODS,
        max_age=86400,
        vary_header=True,
        supports_credentials=False,
    )
    # Match Django's URLConf: no trailing-slash variants and no redirects.
    app.url_map.strict_slashes = False
    app.register_blueprint(bp)

    @app.before_request
    def _method_contract():
        if not request.path.startswith("/api/dss"):
            return None
        if request.path.endswith("/"):
            abort(404)
        if request.method == "HEAD":
            abort(405)
        if request.method == "OPTIONS" and not request.headers.get(
            "Access-Control-Request-Method"
        ):
            abort(405)
        return None

    def _cors_contract(response: Response):
        if not request.path.startswith("/api/dss"):
            return response
        if request.headers.get("Origin"):
            if "Vary" not in response.headers:
                response.headers["Vary"] = "origin"
            if request.method == "OPTIONS" and request.headers.get(
                "Access-Control-Request-Method"
            ):
                # Django's CORS middleware advertised its full configured lists
                # and answered preflight before URL resolution (no Allow).
                response.headers.set(
                    "Access-Control-Allow-Headers", ", ".join(CORS_ALLOW_HEADERS)
                )
                response.headers.set(
                    "Access-Control-Allow-Methods", ", ".join(CORS_ALLOW_METHODS)
                )
                response.headers.set("Access-Control-Max-Age", "86400")
                response.headers.pop("Allow", None)
        return response

    # Run after flask-cors so the fixed header lists win.
    app.after_request_funcs[None].insert(0, _cors_contract)

    @app.errorhandler(404)
    def _not_found(_exc):
        return Response(DJANGO_404, status=404, mimetype="text/html")

    @app.errorhandler(MethodNotAllowed)
    def _method_not_allowed(exc: MethodNotAllowed):
        allowed = RESOURCE_METHODS.get(request.path)
        if allowed is None:
            valid = list(exc.valid_methods or [])
            allowed = [m for m in valid if m not in {"HEAD", "OPTIONS"}] or ["GET"]
        response = Response("", status=405, mimetype="text/html")
        response.headers["Allow"] = ", ".join(allowed)
        return response

    @app.errorhandler(500)
    def _server_error(_exc):
        return Response(DJANGO_500, status=500, mimetype="text/html")

    return app
