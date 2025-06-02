FROM python:3.13-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Update system packages and install essential build dependencies and PostgreSQL
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libssl-dev \
        sqlite3 \
        postgresql \
        postgresql-contrib \
        postgresql-client \
        sudo \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configure PostgreSQL and add appuser to sudoers
USER root
# PostgreSQL will be configured at runtime
RUN echo "appuser ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Upgrade pip to latest version
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements.txt and pyproject.toml first to leverage Docker layer caching
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy only the application code from src layout
COPY src/context_portal_mcp/ ./src/context_portal_mcp/
# Include LICENSE for compliance (optional - uncomment if needed)
# COPY LICENSE ./

# Copy startup and healthcheck scripts
COPY scripts/ ./scripts/

# Install the current project as a package
RUN pip install --no-cache-dir .

# Create directory for logs and data, workspace, set proper ownership and make scripts executable
RUN mkdir -p /data/logs /app/workspace \
    && chown -R appuser:appuser /app /data \
    && chmod +x /app/scripts/*.sh

# Set default environment variables for PostgreSQL
ENV CONPORT_DB_TYPE=postgresql
ENV POSTGRES_HOST=localhost
ENV POSTGRES_PORT=5432
ENV POSTGRES_USER=conport
ENV POSTGRES_PASSWORD=conport
ENV POSTGRES_DB=context_portal

# Switch to non-root user
USER appuser

# Command to run the ConPort server
ENTRYPOINT ["/app/scripts/startup.sh", "python", "-m", "context_portal_mcp.main"]
CMD ["--mode", "http", "--host", "0.0.0.0", "--port", "8000", "--workspace_id", "/app/workspace", "--log-file", "/app/workspace/logs/conport.log", "--log-level", "INFO"]

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD /app/scripts/healthcheck.sh