# Image of the consumer. Build context: the repository root (compose.yaml).
# Contains only common/ and consumer/app/: datasets and the countries
# catalog are mounted at runtime.
FROM python:3.11.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

COPY consumer/requirements.txt /tmp/requirements.txt
RUN pip install --only-binary=:all: --requirement /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Unprivileged runtime user.
RUN groupadd --system --gid 10001 observatory \
    && useradd --system --uid 10001 --gid observatory --no-create-home --shell /usr/sbin/nologin observatory

WORKDIR /app
COPY common ./common
COPY consumer/app ./app

USER observatory
CMD ["python", "-m", "app.main"]
