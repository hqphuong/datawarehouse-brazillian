from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_smorest import Api
# For logging
from logging.config import dictConfig

import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# --- Core config ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
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
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)