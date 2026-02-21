FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ripgrep nodejs npm docker.io && \
    rm -rf /var/lib/apt/lists/*

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

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8090

CMD ["uvicorn", "macaron_platform.server:app", "--host", "0.0.0.0", "--port", "8090", "--ws", "none"]
