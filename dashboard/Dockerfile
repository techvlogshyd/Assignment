FROM python:3.11-slim

# This image is built from the *repo root* so that `qe_toolkit/` (the shared
# QE framework) can be copied in alongside the dashboard. See
# infra/docker-compose.yml — `context: ..` for the dashboard service.

WORKDIR /app
COPY dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY qe_toolkit/ ./qe_toolkit/
COPY dashboard/ .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
