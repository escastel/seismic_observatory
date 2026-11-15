# Image of the API. Build context: the repository root (compose.yaml).
# Contains only common/ and api/app/. The ngrok tunnel is a separate
# compose service (profile "tunnel"), never part of this image.
FROM python:3.11.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --only-binary=:all: --requirement /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Unprivileged runtime user.
RUN groupadd --system --gid 10001 observatory \
    && useradd --system --uid 10001 --gid observatory --no-create-home --shell /usr/sbin/nologin observatory

WORKDIR /app
COPY common ./common
COPY api/app ./app

USER observatory
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
