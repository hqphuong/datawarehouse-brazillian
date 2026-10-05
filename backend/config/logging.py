import json
import logging
import logging.config
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


class DateFolderFileHandler(logging.FileHandler):
    def __init__(self, filename: str, mode: str = "a", encoding=None, delay: bool = False, errors=None):
        log_dir = BACKEND_DIR / "logs" / datetime.now().strftime("%Y-%m-%d")
        log_dir.mkdir(parents=True, exist_ok=True)
        super().__init__(
            filename=str(log_dir / filename),
            mode=mode,
            encoding=encoding,
            delay=delay,
            errors=errors,
        )


class JsonFormatter(logging.Formatter):
    """One JSON object per line for log aggregators (ELK, Datadog)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
        }
        message = record.getMessage()
        # RequestLog already dumps a structured event as the message string â€” promote fields.
        if message.startswith("{") and message.endswith("}"):
            try:
                parsed = json.loads(message)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                payload.update(parsed)
            else:
                payload["message"] = message
        else:
            payload["message"] = message

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info).rstrip()

        return json.dumps(payload, default=str, ensure_ascii=False)


class LoggingConfig:
    def __init__(self, *, debug: bool = True) -> None:
        self.debug = debug

    @property
    def formatters(self) -> dict:
        return {
            "standard": {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "()": "config.logging.JsonFormatter",
            },
        }

    @property
    def handlers(self) -> dict:
        # Local DEBUG keeps human-readable console; prod emits JSON for aggregators.
        console_formatter = "standard" if self.debug else "json"
        return {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": console_formatter,
            },
            "api_prod_file": {
                "class": "config.logging.DateFolderFileHandler",
                "formatter": "json",
                "filename": "api.log",
            },
        }

    @property
    def loggers(self) -> dict:
        return {
            "django": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "api": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "api.prod": {
                "handlers": ["api_prod_file"],
                "level": "INFO",
                "propagate": False,
            },
            "config.env": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        }

    def _build(self) -> dict:
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": self.formatters,
            "handlers": self.handlers,
            "root": {"handlers": ["console"], "level": "INFO"},
            "loggers": self.loggers,
        }

    def bind(self):
        logging.config.dictConfig(self._build())


class Logger:
    django = logging.getLogger("django")
    env = logging.getLogger("config.env")
