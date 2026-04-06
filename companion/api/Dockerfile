FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY config.py .
COPY app/ ./app/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["python", "-u", "app/main.py"]