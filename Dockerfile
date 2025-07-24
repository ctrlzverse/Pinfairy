# Multi-stage Dockerfile for Pinfairy Bot
# Stage 1: Builder
FROM python:3.11-slim as builder

# Set environment variables for build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Production
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Install Playwright and browsers
RUN playwright install chromium && \
    playwright install-deps chromium

# Create non-root user for security
RUN groupadd -r pinfairy && useradd -r -g pinfairy pinfairy

# Create app directory
WORKDIR /app

# Copy application code
COPY --chown=pinfairy:pinfairy . .

# Create necessary directories with proper permissions
RUN mkdir -p logs downloads backups && \
    chown -R pinfairy:pinfairy logs downloads backups && \
    chmod 755 logs downloads backups

# Switch to non-root user
USER pinfairy

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio, sys; sys.exit(0)" || exit 1

# Expose port for health checks (optional)
EXPOSE 8080

# Run the bot
CMD ["python", "bot.py"]
