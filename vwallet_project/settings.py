import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

DJ_WALLET_SIGNING_SECRET = os.environ.get(
    "DJ_WALLET_SIGNING_SECRET", "dev-signing-secret-change-me"
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "dj_wallet",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "vwallet_project.urls"

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
    }
]

WSGI_APPLICATION = "vwallet_project.wsgi.application"
ASGI_APPLICATION = "vwallet_project.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Phnom_Penh"
USE_I18N = True
USE_TZ = True

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/api/"

CSRF_FAILURE_VIEW = "dj_wallet.csrf.csrf_failure"

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "dj_wallet.api.throttles.BurstRateThrottle",
        "dj_wallet.api.throttles.SustainedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "wallet_burst": "60/min",
        "wallet_sustained": "1000/day",
    },
}

# Celery
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_BEAT_SCHEDULE = {
    "anchor-pending-every-10s": {
        "task": "dj_wallet.tasks.submit_pending_anchors",
        "schedule": 10.0,
        "args": (100,),
    },
    "anchor-confirm-every-20s": {
        "task": "dj_wallet.tasks.confirm_submitted_anchors",
        "schedule": 20.0,
        "args": (100,),
    },
}

# Besu anchoring (local)
DJ_WALLET_CHAIN_ADAPTER = "dj_wallet.chain.besu.BesuAdapter"
DJ_WALLET_CHAIN_RPC_URL = os.environ.get("DJ_WALLET_CHAIN_RPC_URL", "http://127.0.0.1:8545")
DJ_WALLET_CHAIN_ID = int(os.environ.get("DJ_WALLET_CHAIN_ID", "20260321"))
DJ_WALLET_ANCHOR_CONTRACT_ADDRESS = os.environ.get(
    "DJ_WALLET_ANCHOR_CONTRACT_ADDRESS",
    "0xC6d213e289d1F1aAe51E567DeaC4E5CE7e17ad23",
)
DJ_WALLET_CHAIN_PRIVATE_KEY = os.environ.get("DJ_WALLET_CHAIN_PRIVATE_KEY", "")
