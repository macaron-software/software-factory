FROM python:3.12-slim

WORKDIR /app

# System deps + Node.js 20 + security scanners
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl gnupg ripgrep && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Python deps + SAST tools
COPY platform/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    bandit semgrep

# Playwright (chromium only, minimal)
RUN npx -y playwright install --with-deps chromium

# Copy platform code
COPY platform/ /app/platform/
COPY cli/ /app/cli/
COPY skills/ /app/skills/
COPY mcp_lrm/ /app/mcp_lrm/
COPY dashboard/ /app/dashboard/
COPY projects/ /app/projects/

# Data + workspace dirs
RUN mkdir -p /app/data /app/workspace

# Create non-root user
RUN groupadd -r macaron && useradd -r -g macaron -d /app macaron \
    && chown -R macaron:macaron /app
USER macaron

# Env
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV WORKSPACE_ROOT=/app/workspace
ENV PLATFORM_LLM_PROVIDER=demo
ENV PLATFORM_LLM_MODEL=demo

EXPOSE 8099

CMD ["uvicorn", "platform.server:app", "--host", "0.0.0.0", "--port", "8099", "--ws", "none"]
