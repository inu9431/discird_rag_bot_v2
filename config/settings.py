import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

# env 초기화
env = environ.Env(
    # 기본 값
    DEBUG=(bool, False)
)

# env 파일 읽기
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# Ensure lowercase logs directory exists and is used consistently
LOG_BASE_DIR = Path(LOG_DIR)
if not LOG_BASE_DIR.exists():
    LOG_BASE_DIR.mkdir()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name} {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        # 콘솔(터미널)에 출력
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        # 파일에 저장 (일일 회전)
        "file": {
            "level": "INFO",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "django.log"),
            "when": "midnight",  # 자정에 매일 새로운 파일 생성
            "interval": 1,
            "backupCount": 30,  # 30일 보관
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        # 우리 앱 전용 로거
        "archiver": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

# Build paths inside the project like this: BASE_DIR / 'subdir'.


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# load SECRET_KEY from environment (.env). Provide a safe default for local dev only.
SECRET_KEY = env("SECRET_KEY", default="django-insecure-please-set-secret-in-env")

# SECURITY WARNING: don't run with debug turned on in production!
# Read DEBUG from env (bool conversion)
DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "web", "*"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "archiver",
    "import_export",
    "rest_framework",
    "django_q",
    "drf_spectacular",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": env.db(
        "DATABASE_URL", default="postgres://bot_user:bot_password@localhost:5432/bot_db"
    )
}

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")


Q_CLUSTER = {
    "name": "discord_qna_cluster",
    "workers": 4,
    "recycle": 500,
    "timeout": 60,
    "retry": 300,  # 실패 시 300초(5분) 후에 다시 시도! (우리가 sleep 할 필요 없음)
    "orm": "default",
}

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# OpenAI (임베딩)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Discord
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Notion
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")
NOTION_BOARD_URL = os.getenv("NOTION_BOARD_URL")

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Discord QnA Archiver API",
    "DESCRIPTION": "Discord 봇의 질문-답변 아카이빙 API",
    "VERSION": "1.0.0",
}
