FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2 \
    libffi-dev \
    libgdk-pixbuf-2.0-0 \
    libharfbuzz0b \
    libjpeg62-turbo-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    shared-mime-info \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN grep -v '^pkg-resources==' /app/requirements.txt > /tmp/requirements.txt \
    && pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt

COPY . /app

RUN mkdir -p /app/.django_cache /app/data /app/media /app/staticfiles \
    && chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "interactive_video.wsgi:application", "-c", "/app/gunicorn.conf.py"]
