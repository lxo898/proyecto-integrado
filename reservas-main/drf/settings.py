"""
Django settings for drf project.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# === Seguridad (solo dev) ===
SECRET_KEY = 'django-insecure-h1xmy3@$x#v1&8c719*z#e1^whtpxifv)3(847ik%iya2qfk@i'
DEBUG = True
ALLOWED_HOSTS = []  # en producción cámbialo

# === Apps ===
INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Tu app
    'api',
    # Opcional si usarás DRF
    'rest_framework',
]

# === Middleware ===
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'drf.urls'

# === Templates ===
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
        ],
    },
}]

WSGI_APPLICATION = 'drf.wsgi.application'

# === Base de datos ===
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# === Password validators ===
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# === Internacionalización ===
LANGUAGE_CODE = 'es'                 # interfaz y formatos en español
TIME_ZONE = 'America/Santiago'       # zona horaria Chile
USE_I18N = True
USE_TZ = True

# === Archivos estáticos (dev) ===
STATIC_URL = 'static/'
# Si tendrás una carpeta /static en el root del proyecto, descomenta:
# from pathlib import Path
# STATICFILES_DIRS = [BASE_DIR / "static"]

# === Auth: rutas de login/logout ===
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard_user"
LOGOUT_REDIRECT_URL = "login"

# === Primary key por defecto ===
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
