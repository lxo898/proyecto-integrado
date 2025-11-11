"""
Django settings for drf project (INACAP · Reservas).
Listo para dev con SQLite y preparado para PostgreSQL/AWS por variables de entorno.
"""

from pathlib import Path
import os
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# Seguridad / Debug
# =============================================================================
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-h1xmy3@$x#v1&8c719*z#e1^whtpxifv)3(847ik%iya2qfk@i"  # SOLO DEV
)
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"

# Hosts comunes en dev; en prod usa variables de entorno
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

# Si despliegas detrás de un dominio/ALB, agrega su origen aquí por env
_default_csrf = "http://127.0.0.1:8000,http://localhost:8000"
CSRF_TRUSTED_ORIGINS = os.getenv("DJANGO_CSRF_TRUSTED", _default_csrf).split(",")

# =============================================================================
# Apps
# =============================================================================
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Proyecto
    "api",

    # DRF (opcional)
    "rest_framework",
]

# =============================================================================
# Middleware
# =============================================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "drf.urls"

# =============================================================================
# Templates
# =============================================================================
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],   # carpeta templates en el root
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "api.context_processors.notifications_unread",

        ],
    },
}]

WSGI_APPLICATION = "drf.wsgi.application"

# =============================================================================
# Base de datos
# - Dev: SQLite
# - Prod: PostgreSQL vía env (DB_URL = postgres://USER:PASS@HOST:PORT/NAME)
# =============================================================================
def parse_db_url(url: str):
    """
    Parser simple para DATABASE_URL estilo postgres://user:pass@host:port/db
    """
    parsed = urlparse(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username,
        "PASSWORD": parsed.password,
        "HOST": parsed.hostname,
        "PORT": parsed.port or "5432",
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),  # pool básico
        "OPTIONS": {},
    }

DATABASES = {}
DB_URL = os.getenv("DB_URL") or os.getenv("DATABASE_URL")

if DB_URL:
    DATABASES["default"] = parse_db_url(DB_URL)
else:
    # Por defecto, SQLite en dev
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }

# =============================================================================
# Password validators
# =============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =============================================================================
# Internacionalización
# =============================================================================
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# =============================================================================
# Archivos estáticos y media
# =============================================================================
# Static (referenciados por templates) — en dev
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
# En prod (collectstatic → S3 o disco)
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media (subidas de usuario, ej. fotos de espacios)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Cache headers para staticfiles (mejorable con S3/CloudFront en AWS)
STATICFILES_STORAGE = os.getenv(
    "DJANGO_STATICFILES_STORAGE",
    "django.contrib.staticfiles.storage.ManifestStaticFilesStorage" if not DEBUG else
    "django.contrib.staticfiles.storage.StaticFilesStorage"
)

# =============================================================================
# Autenticación (login/logout)
# =============================================================================
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard_user"
LOGOUT_REDIRECT_URL = "login"

# =============================================================================
# DRF (opcional)
# =============================================================================
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": int(os.getenv("API_PAGE_SIZE", "20")),
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        # Habilita Browsable API solo en DEBUG
        *([] if not DEBUG else ["rest_framework.renderers.BrowsableAPIRenderer"]),
    ],
}

# =============================================================================
# Email (consola en dev; SMTP en prod por variables de entorno)
# =============================================================================
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@inacap.cl")

# =============================================================================
# Seguridad adicional en producción
# =============================================================================
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "true").lower() == "true"
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# =============================================================================
# Logging (útil para AWS/CloudWatch)
# =============================================================================
LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name} :: {message}",
            "style": "{",
        },
        "simple": {"format": "[{levelname}] {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
}

# =============================================================================
# Flags / Constantes de negocio del proyecto
# =============================================================================
# Ventana mínima para que el usuario pueda cancelar (horas antes del inicio)
MIN_CANCEL_WINDOW_HOURS = int(os.getenv("MIN_CANCEL_WINDOW_HOURS", "2"))

# Buffers por espacio (si luego lo parametrizas por modelo, estos son defaults)
DEFAULT_BUFFER_BEFORE_MIN = int(os.getenv("DEFAULT_BUFFER_BEFORE_MIN", "0"))
DEFAULT_BUFFER_AFTER_MIN  = int(os.getenv("DEFAULT_BUFFER_AFTER_MIN", "0"))

# Tamaño de página genérico para listados (cuando actives paginación en vistas)
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "20"))

# Feature flags simples
FEATURE_ICS_EXPORT = os.getenv("FEATURE_ICS_EXPORT", "true").lower() == "true"
FEATURE_WAITLIST    = os.getenv("FEATURE_WAITLIST", "false").lower() == "true"

# =============================================================================
# Primary key por defecto
# =============================================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# === Notificaciones a personal de aseo ===
CLEANING_GROUP_NAME = os.getenv("CLEANING_GROUP_NAME", "Aseo")  # nombre del grupo en Django
SEND_EMAIL_TO_CLEANING = os.getenv("SEND_EMAIL_TO_CLEANING", "true").lower() == "true"

