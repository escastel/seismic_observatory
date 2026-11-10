FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY producer/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY producer/app ./app
COPY db/seeds ./data/seeds

CMD ["python", "-m", "app.main"]
