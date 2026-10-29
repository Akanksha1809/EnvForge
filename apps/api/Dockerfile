FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# No Terraform/kubectl here: only app/services/provisioning.py shells out to
# them, and that module is only ever called from the Celery worker
# (app/workers/tasks/provisioning.py) — the uvicorn API process never
# provisions anything directly, it only enqueues jobs. Embedding those
# binaries in this image (as an earlier copy-paste from Dockerfile.worker
# did) only bloated the build and doubled this image's exposure to their
# vendored Go dependencies' CVEs for no functional reason.

RUN pip install uv

WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -e . --group dev || uv pip install --system --no-cache -e .

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
