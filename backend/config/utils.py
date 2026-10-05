import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

_TRUTHY_VALUES = {"1", "true", "yes", "on"}


class Field:
    def __init__(
        self,
        key: str,
        default: str = "",
        transform: Callable[[str], Any] = lambda value: value,
        mask: bool = False,
        required: bool = False,
    ):
        self.name = ""
        self.key = key
        self.default = default
        self.transform = transform
        self.mask = mask
        self.required = required

    def resolve(self, raw_value: str) -> Any:
        if self.required and not raw_value:
            raise ImproperlyConfigured(f"{self.key} is required")
        return self.transform(raw_value)

    def read(self) -> Any:
        raw_value = os.environ.get(self.key, self.default)
        return self.resolve(raw_value)


class EnvConfigMeta(type):
    _declared_fields: dict[str, Field]

    def __new__(mcls, name, bases, namespace):
        fields: dict[str, Field] = {}
        for base in bases:
            fields.update(getattr(base, "_declared_fields", {}))

        for attr_name, attr_value in namespace.items():
            if isinstance(attr_value, Field):
                attr_value.name = attr_name
                fields[attr_name] = attr_value

        namespace["_declared_fields"] = fields
        return super().__new__(mcls, name, bases, namespace)

    def __call__(cls, *args, **kwargs):
        module = sys.modules[cls.__module__]
        module_file = getattr(module, "__file__", None)
        if module_file is not None:
            load_dotenv(Path(module_file).resolve().parent.parent / ".env")

        instance = super().__call__(*args, **kwargs)
        for attr_name, field in cls._declared_fields.items():
            setattr(instance, attr_name, field.read())

        if cls.should_log_loaded_variables():
            cls.log_loaded_variables(instance, logging.getLogger(cls.__module__))
        return instance

    def should_log_loaded_variables(cls) -> bool:
        if "runserver" in sys.argv:
            return os.environ.get("RUN_MAIN") == "true"
        return True

    def log_loaded_variables(cls, instance, logger):
        fields = []
        for attr_name, field in cls._declared_fields.items():
            value = getattr(instance, attr_name)
            if field.mask:
                value = Utils.mask(value)
            fields.append((field.key, value))

        key_width = max(len(key) for key, _ in fields)
        lines = ["", "Staring server:"]
        lines.extend(f"  {key:<{key_width}} = {value}" for key, value in fields)
        logger.info("\n".join(lines))


class Utils:
    @staticmethod
    def parse_bool(value: str | bool) -> bool:
        if isinstance(value, bool):
            return value
        return value.strip().lower() in _TRUTHY_VALUES

    @staticmethod
    def parse_int_in_range(name: str, value: str | int, *, minimum: int, maximum: int) -> int:
        if isinstance(value, int):
            parsed = value
        else:
            try:
                parsed = int(value)
            except ValueError as exc:
                raise ImproperlyConfigured(f"{name} must be an integer") from exc

        if parsed < minimum or parsed > maximum:
            raise ImproperlyConfigured(f"{name} must be between {minimum} and {maximum}")
        return parsed

    @staticmethod
    def parse_list(value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return [item.strip() for item in value if item and item.strip()]

        raw = value.strip()
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def mask(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 4:
            return "*" * len(value)
        return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
