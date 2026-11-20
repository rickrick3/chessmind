from .settings import *  # noqa: F401,F403

# Shallow engine, no AI calls, Celery tasks run inline.
ENGINE_DEPTH = 8
AI_PROVIDER = "none"
CELERY_TASK_ALWAYS_EAGER = True
