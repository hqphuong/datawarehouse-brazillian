from .utils import EnvConfigMeta, Field, Utils


class EnvConfig(metaclass=EnvConfigMeta):
    SECRET_KEY = Field("SECRET_KEY", default="", mask=True, required=True)
    DEBUG = Field("DJANGO_DEBUG", default="true", transform=Utils.parse_bool)
    ALLOWED_HOSTS = Field("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1,0.0.0.0", transform=Utils.parse_list)
    USE_X_FORWARDED = Field("DJANGO_USE_X_FORWARDED", default="false", transform=Utils.parse_bool)
    POSTGRES_DB = Field("POSTGRES_DB", default="tam_soat_dot_quy")
    POSTGRES_USER = Field("POSTGRES_USER", default="postgres")
    POSTGRES_PASSWORD = Field("POSTGRES_PASSWORD", default="password", mask=True)
    POSTGRES_HOST = Field("POSTGRES_HOST", default="localhost")
    POSTGRES_PORT = Field("POSTGRES_PORT", default="5432")
    PATIENT_CODE_LENGTH = Field(
        "PATIENT_CODE_LENGTH",
        default="6",
        transform=lambda value: Utils.parse_int_in_range(
            "PATIENT_CODE_LENGTH",
            value,
            minimum=1,
            maximum=32,
        ),
    )
    TENANT_DEFAULT_CODE = Field("TENANT_DEFAULT_CODE", default="default")
    TENANT_DEFAULT_SCHEMA = Field("TENANT_DEFAULT_SCHEMA", default="tenant_default")
    TENANT_DEFAULT_DOMAIN = Field("TENANT_DEFAULT_DOMAIN", default="localhost")
    RBAC_ENFORCED = Field("RBAC_ENFORCED", default="true", transform=Utils.parse_bool)

    PUBLIC_API_RATE_LIMIT_ENABLED = Field("PUBLIC_API_RATE_LIMIT_ENABLED", default="true", transform=Utils.parse_bool)
    PUBLIC_API_RATE_LIMIT = Field(
        "PUBLIC_API_RATE_LIMIT",
        default="60",
        transform=lambda v: Utils.parse_int_in_range("PUBLIC_API_RATE_LIMIT", v, minimum=1, maximum=10_000),
    )
    PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS = Field(
        "PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS",
        default="60",
        transform=lambda v: Utils.parse_int_in_range(
            "PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS",
            v,
            minimum=1,
            maximum=86_400,
        ),
    )

    EMAIL_BACKEND = Field("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
    EMAIL_HOST = Field("EMAIL_HOST", default="")
    EMAIL_PORT = Field("EMAIL_PORT", default="587")
    EMAIL_HOST_USER = Field("EMAIL_HOST_USER", default="", mask=True)
    EMAIL_HOST_PASSWORD = Field("EMAIL_HOST_PASSWORD", default="", mask=True)
    EMAIL_USE_TLS = Field("EMAIL_USE_TLS", default="true", transform=Utils.parse_bool)
    DEFAULT_FROM_EMAIL = Field("DEFAULT_FROM_EMAIL", default="")
    FRONTEND_URL = Field("FRONTEND_URL", default="http://localhost:8080")
    # Comma-separated browser origins allowed when CORS credentials are enabled.
    CORS_ALLOWED_ORIGINS = Field(
        "CORS_ALLOWED_ORIGINS",
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080",
        transform=Utils.parse_list,
    )
    # Empty = auto (Secure when DJANGO_DEBUG=false). Set false for HTTP-only test hosts.
    AUTH_COOKIE_SECURE = Field(
        "AUTH_COOKIE_SECURE",
        default="",
        transform=lambda v: None if str(v).strip() == "" else Utils.parse_bool(v),
    )
