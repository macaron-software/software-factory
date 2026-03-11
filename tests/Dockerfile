# Dockerfile for TMA Auto-Heal Test Environment
# Builds test environment for project-setup phase validation

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy test files
COPY tests/ ./tests/
COPY tests/fixtures/ ./tests/fixtures/

# Copy source modules
COPY workflows/ ./workflows/
COPY src/ ./src/

# Test environment variables
ENV PYTHONPATH=/app
ENV TEST_ENV=local
ENV LOG_LEVEL=DEBUG

# Run tests
CMD ["pytest", "-v", "--tb=short", "tests/test_phase_diagnostic.py"]
