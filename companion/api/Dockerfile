FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY config.py .
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY app/ ./app/
COPY scripts/ ./scripts/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["python", "-u", "app/main.py"]