"""WSGI entry point for the Flask DSS backend.

Development:  flask --app wsgi run --debug
Production:   gunicorn "wsgi:application"  (Linux/macOS)
              waitress-serve --listen=0.0.0.0:8000 wsgi:application  (Windows)
"""

from dss.app import create_app

app = create_app()
application = app
