from .settings import *  # noqa: F401,F403

# Shallow engine, no AI calls, Celery tasks run inline.
ENGINE_DEPTH = 8
AI_PROVIDER = "none"
CELERY_TASK_ALWAYS_EAGER = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
