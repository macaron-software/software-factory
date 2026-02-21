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
COPY core/ /app/core/
COPY skills/ /app/skills/

# Create non-root user
RUN groupadd -r macaron && useradd -r -g macaron -d /app macaron \
    && chown -R macaron:macaron /app
USER macaron

# Env
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8090

CMD ["uvicorn", "platform.server:app", "--host", "0.0.0.0", "--port", "8090"]
