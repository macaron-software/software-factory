FROM python:3.12-slim

LABEL maintainer="Software Factory Team"
LABEL description="Software Factory Dashboard - Monitoring Interface"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/projects /tmp/factory

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Environment variables
ENV DASHBOARD_PORT=8080
ENV DASHBOARD_HOST=0.0.0.0
ENV DASHBOARD_DEBUG=false
ENV DASHBOARD_LOG_LEVEL=warning

# Run the application
CMD ["python3", "server.py"]
