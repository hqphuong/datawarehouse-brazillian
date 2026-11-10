import os
import sys
from pathlib import Path
from logging.config import dictConfig
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_smorest import Api
from dotenv import load_dotenv

# Ensure backend directory and repo root are in sys.path
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Alias __main__ to 'app' in sys.modules to prevent circular re-import when executed directly
if __name__ == '__main__':
    sys.modules['app'] = sys.modules['__main__']

# Load .env from backend/.env first, then fallback to repo root .env
load_dotenv(BASE_DIR / ".env")
load_dotenv(REPO_ROOT / ".env")

app = Flask(__name__)

# --- Port & Host resolution helper ---
def resolve_port_and_host():
    """
    Resolve port and host checking:
    1. BACKEND_PORT / BACKEND_HOST
    2. PORT / HOST
    3. FLASK_RUN_PORT / FLASK_RUN_HOST
    4. Default: 5000, '127.0.0.1'
    """
    port_val = os.getenv('BACKEND_PORT') or os.getenv('PORT') or os.getenv('FLASK_RUN_PORT') or '5000'
    try:
        resolved_port = int(port_val)
    except (ValueError, TypeError):
        resolved_port = 5000
    resolved_host = os.getenv('BACKEND_HOST') or os.getenv('HOST') or os.getenv('FLASK_RUN_HOST') or '127.0.0.1'
    return resolved_host, resolved_port

db_url = os.getenv('DATABASE_URL')
if not db_url:
    pg_user = os.getenv('POSTGRES_USER', 'postgres')
    pg_pass = os.getenv('POSTGRES_PASSWORD', '')
    pg_host = os.getenv('POSTGRES_HOST', 'localhost')
    pg_port = os.getenv('POSTGRES_PORT', '5432')
    pg_db = os.getenv('POSTGRES_DB', 'brazillian')
    auth = f"{pg_user}:{pg_pass}@" if pg_pass else f"{pg_user}@"
    db_url = f"postgresql://{auth}{pg_host}:{pg_port}/{pg_db}"

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- OpenAPI / Swagger config ---
app.config['API_TITLE'] = 'Olist Logistics DSS API'
app.config['API_VERSION'] = 'v1'
app.config["OPENAPI_VERSION"] = "3.0.2"
app.config["OPENAPI_URL_PREFIX"] = "/"
app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger-ui"
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

db = SQLAlchemy(app)
api = Api(app)

# Configure logger
log_level = os.getenv('LOG_LEVEL') or 'INFO'
dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': log_level,
        'handlers': ['wsgi']
    }
})
logger = app.logger

# --- Register blueprint ---
from routes import blp
api.register_blueprint(blp)

if __name__ == '__main__':
    '''When running via `flask run` or `flask --app ... run`, Click ignores app.run() and does
    not read BACKEND_PORT or PORT by default.'''
    host, port = resolve_port_and_host()
    app.run(host=host, port=port, debug=True)
