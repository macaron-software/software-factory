FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ripgrep nodejs npm docker.io && \
    rm -rf /var/lib/apt/lists/* && \
    git config --global --add safe.directory "*"

COPY platform/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Playwright for browser screenshots (agent evidence)
RUN pip install --no-cache-dir playwright && \
    playwright install --with-deps chromium

COPY platform/ /app/macaron_platform/
COPY core/ /app/core/
COPY skills/ /app/skills/
COPY projects/ /app/projects/
COPY mf_projects/ /app/mf_projects/

# Create non-root user (needs docker group for container tools)
RUN groupadd -r macaron && useradd -r -g macaron -G docker -d /app macaron \
    && mkdir -p /app/data/logs \
    && chown -R macaron:macaron /app
USER macaron

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8090

CMD ["sh", "-c", "git config --global --add safe.directory '*' && uvicorn macaron_platform.server:app --host 0.0.0.0 --port 8090 --ws none"]
