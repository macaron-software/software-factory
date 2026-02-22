FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ripgrep nodejs npm ca-certificates gnupg && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y --no-install-recommends docker-ce-cli && \
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
COPY mcp_lrm/ /app/mcp_lrm/

# Remove personal/local-only project configs (not deployed to Azure)
RUN rm -f /app/projects/ppz.yaml /app/projects/psy.yaml \
          /app/projects/yolonow.yaml /app/projects/fervenza.yaml

# Capture build info
RUN echo "built $(date -u +%Y-%m-%dT%H:%M:%SZ)" > /app/VERSION

# Create non-root user (docker group GID must match host's docker socket GID)
RUN groupadd -r -g 988 docker-host && groupadd -r macaron \
    && useradd -r -g macaron -G docker-host -d /app macaron \
    && mkdir -p /app/data/logs \
    && chown -R macaron:macaron /app
USER macaron

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8090

CMD ["sh", "-c", "git config --global --add safe.directory '*' && uvicorn macaron_platform.server:app --host 0.0.0.0 --port 8090 --ws none"]
