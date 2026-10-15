# Image that Kestra uses to run our Python ingestion scripts, one temporary container per task.
#   docker build -t deng-rail-weather:local .
# Rebuild after every change to ingestion/ or sql/, otherwise Kestra runs the old code.
FROM python:3.13.11-slim-bookworm

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ingestion ./ingestion
COPY sql ./sql

RUN useradd --create-home pipeline
USER pipeline

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python"]
CMD ["-m", "ingestion.transport", "--help"]