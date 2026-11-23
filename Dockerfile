FROM python:3.12-slim
# Stockfish from Debian: GPL-3.0, runs as a separate process (UCI). Builds on arm64 and amd64.
RUN apt-get update && apt-get install -y --no-install-recommends stockfish gettext \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# zstd reads the Lichess puzzle file (.csv.zst) for the import_puzzles command.
RUN apt-get update && apt-get install -y --no-install-recommends zstd && rm -rf /var/lib/apt/lists/*
COPY . .
RUN python manage.py collectstatic --noinput && python manage.py compilemessages
