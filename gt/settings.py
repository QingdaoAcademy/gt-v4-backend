import os
import sys
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG = yaml.safe_load((BASE_DIR / "config.yaml").read_text())

MODE = CONFIG["mode"]

SECRET_KEY = CONFIG["secret_key"]

ALI_ACCESS_KEY = CONFIG["ali_access_key"]
ALI_ACCESS_SECRET = CONFIG["ali_access_secret"]

DOGE_ACCESS = CONFIG["doge_access"]
DOGE_SECRET = CONFIG["doge_secret"]
DOGE_FILE_CDNKEY = CONFIG["doge_file_cdnkey"]

OPENAI_API_KEY = CONFIG["openai_api_key"]
OPENAI_BASE_URL = CONFIG["openai_base_url"]

DB_SQLITE = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": BASE_DIR / "db.sqlite3",
}

DB_MYSQL = {
    "ENGINE": "django.db.backends.mysql",
    "OPTIONS": {
        "read_default_file": (
            (BASE_DIR / "db.cnf").relative_to(Path.cwd()).__str__()
            if sys.platform.startswith("win32")
            else str(BASE_DIR / "db.cnf")
        ),
    },
}

DB_POSTGRES = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "gt",
    "USER": "srv",
    "HOST": "127.0.0.1",
    "PORT": "5432",
}

if MODE.startswith("dev"):
    DEBUG = True
    if MODE == "dev-mysql":
        DATABASES = {"default": DB_MYSQL}
    else:
        DATABASES = {"default": DB_SQLITE}
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "dev_cache",
        }
    }
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    DEBUG = False
    DATABASES = {"default": DB_POSTGRES}
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://127.0.0.1:6379/4",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = CONFIG["email_host"]
    EMAIL_PORT = CONFIG["email_port"]
    EMAIL_HOST_USER = CONFIG["email_host_user"]
    EMAIL_HOST_PASSWORD = CONFIG["email_host_password"]
    EMAIL_USE_TLS = CONFIG["email_use_tls"]
    EMAIL_USE_SSL = CONFIG["email_use_ssl"]
    EMAIL_TIMEOUT = CONFIG["email_timeout"]
    EMAIL_SSL_KEYFILE = CONFIG["email_ssl_keyfile"]
    EMAIL_SSL_CERTFILE = CONFIG["email_ssl_certfile"]

ALLOWED_HOSTS = ["*"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "gt_auth",
    "gt_forum",
    "gt_file",
    "gt_admin",
    "gt_coin",
    "gt_alumni",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "gt.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "gt.wsgi.application"


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "zh-hans"

TIME_ZONE = "Asia/Shanghai"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = "/static/"

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


AUTH_USER_MODEL = "gt_auth.User"


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["gt.authentication.JWTAuthentication"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "gt.paginations.PageNumberPagination",
    "EXCEPTION_HANDLER": "gt.middlewares.gt_exception_handler",
}

CELERY_TIMEZONE = TIME_ZONE
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_BROKER_URL = "redis://127.0.0.1:6379/4"
# CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/4"
