# Test runner image: pytest, the dependencies of every service and the psql
# client used by db/sql/apply.sh. Test code is bind mounted, not copied.
FROM python:3.11.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN apt-get update \
    && apt-get install --yes --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY tests/requirements.txt /tmp/requirements.txt
RUN pip install --only-binary=:all: --requirement /tmp/requirements.txt

WORKDIR /repo
# Runs as root on purpose: it is a development-only container that writes
# evidence into the bind-mounted docs/evidence directory. With rootless Docker
# (and Docker Desktop) that root maps to the invoking user, so the files keep
# the user's ownership. The service images run as an unprivileged user.
CMD ["pytest", "tests/db", "-v"]
