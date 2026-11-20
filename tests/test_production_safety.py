import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_production_refuses_default_secret_key():
    env = {k: v for k, v in os.environ.items() if k != "DJANGO_SECRET_KEY"}
    env.update(DJANGO_DEBUG="0", DJANGO_SETTINGS_MODULE="config.settings")
    r = subprocess.run([sys.executable, "-c", "import django; django.setup()"], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    assert r.returncode != 0 and "DJANGO_SECRET_KEY" in r.stderr


def test_docker_image_excludes_secrets_and_scratch():
    ignored = (ROOT / ".dockerignore").read_text().split()
    assert {".env", ".git", ".superpowers"} <= set(ignored)
