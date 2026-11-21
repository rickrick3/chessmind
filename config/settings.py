import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


DEBUG = env("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-change-me" if DEBUG else None)
if not SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG=0.")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [o for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "players",
    "games",
    "analysis",
    "accounts",
    "curriculum",
    "learning",
    "gamification",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.LearnerMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.contrib.messages.context_processors.messages",
                "players.context.player",
                "accounts.context.learner",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "chess"),
        "USER": env("POSTGRES_USER", "chess"),
        "PASSWORD": env("POSTGRES_PASSWORD", "chess"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# Accounts: guests keep their progress in a long-lived session.
SESSION_COOKIE_AGE = 365 * 24 * 3600
LOGIN_URL = "/login/"
GUEST_IDLE_DAYS = 180
DAILY_GOAL_CHOICES = (10, 20, 30, 50)
DAILY_GOAL_DEFAULT = 20
LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW = 15 * 60  # seconds

# Email (password reset). Console in development; any SMTP service in production.
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "ChessMind <no-reply@localhost>")
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
LANGUAGES = [("fr", "Français"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_I18N = True
TIME_ZONE = "UTC"
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", "redis://localhost:6379/0"),
    }
}

CELERY_BROKER_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_ALWAYS_EAGER = env("CELERY_TASK_ALWAYS_EAGER", "0") == "1"
CELERY_TASK_EAGER_PROPAGATES = False
# Lesson generation and validation run on their own queue so game reviews stay fast.
CELERY_TASK_ROUTES = {"curriculum.tasks.*": {"queue": "content"}}

# Engine
ENGINE_PATH = env("ENGINE_PATH", "/usr/games/stockfish")
ENGINE_DEPTH = int(env("ENGINE_DEPTH", "18"))
ENGINE_MULTIPV = 3

# Weekly limits (ISO week, UTC)
LIMIT_REVIEWS_PER_WEEK = int(env("LIMIT_REVIEWS_PER_WEEK", "5"))
LIMIT_EXPLAINS_PER_WEEK = int(env("LIMIT_EXPLAINS_PER_WEEK", "20"))

# AI
AI_PROVIDER = env("AI_PROVIDER", "gemini")  # "gemini" or "none"
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = env("GEMINI_API_KEY", "")

# Chess.com asks API clients to identify themselves with a contact.
CHESSCOM_USER_AGENT = env("CHESSCOM_USER_AGENT", "ChessCoach/0.1 (contact: rickrick20050@gmail.com)")
