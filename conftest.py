import os

# Test settings: shallow engine, no AI calls, Celery runs inline.
os.environ.setdefault("ENGINE_DEPTH", "8")
os.environ.setdefault("AI_PROVIDER", "none")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")
