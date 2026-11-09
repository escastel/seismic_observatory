FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY consumer/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY consumer/app ./app

CMD ["python", "-m", "app.main"]
