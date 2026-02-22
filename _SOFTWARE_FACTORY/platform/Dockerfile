FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY platform/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy platform code
COPY platform/ /app/platform/
COPY cli/ /app/cli/
COPY skills/ /app/skills/
COPY mcp_lrm/ /app/mcp_lrm/
COPY dashboard/ /app/dashboard/
COPY projects/ /app/projects/

# Data dir
RUN mkdir -p /app/data

# Create non-root user
RUN groupadd -r macaron && useradd -r -g macaron -d /app macaron \
    && chown -R macaron:macaron /app
USER macaron

# Env
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PLATFORM_LLM_PROVIDER=demo
ENV PLATFORM_LLM_MODEL=demo

EXPOSE 8099

CMD ["uvicorn", "platform.server:app", "--host", "0.0.0.0", "--port", "8099", "--ws", "none"]
