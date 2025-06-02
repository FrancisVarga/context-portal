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

# Install the current project as a package
RUN pip install --no-cache-dir .

# Create directory for logs and data, workspace, set proper ownership
RUN mkdir -p /data/logs /app/workspace \
    && chown -R appuser:appuser /app /data

# Set default environment variables for PostgreSQL
ENV CONPORT_DB_TYPE=postgresql
ENV POSTGRES_HOST=localhost
ENV POSTGRES_PORT=5432
ENV POSTGRES_USER=conport
ENV POSTGRES_PASSWORD=conport
ENV POSTGRES_DB=context_portal

# Create startup script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Initialize PostgreSQL if needed\n\
if [ ! -f /var/lib/postgresql/*/main/PG_VERSION ]; then\n\
  echo "Initializing PostgreSQL database..."\n\
  sudo -u postgres /usr/lib/postgresql/*/bin/initdb -D /var/lib/postgresql/*/main\n\
fi\n\
\n\
# Start PostgreSQL\n\
echo "Starting PostgreSQL..."\n\
sudo -u postgres /usr/lib/postgresql/*/bin/pg_ctl -D /var/lib/postgresql/*/main -l /var/log/postgresql/postgresql.log start\n\
\n\
# Wait for PostgreSQL to start\n\
echo "Waiting for PostgreSQL to start..."\n\
while ! sudo -u postgres pg_isready; do\n\
  echo "Still waiting for PostgreSQL..."\n\
  sleep 1\n\
done\n\
\n\
# Create database user and database if they dont exist\n\
echo "Setting up database..."\n\
sudo -u postgres psql -c "SELECT 1 FROM pg_user WHERE usename = '\''conport'\'';" | grep -q 1 || \\\n\
  sudo -u postgres psql -c "CREATE USER conport WITH SUPERUSER PASSWORD '\''conport'\'';" || true\n\
\n\
sudo -u postgres psql -lqt | cut -d \\| -f 1 | grep -qw context_portal || \\\n\
  sudo -u postgres createdb -O conport context_portal || true\n\
\n\
echo "PostgreSQL setup complete."\n\
\n\
# Execute the main command\n\
exec "$@"' > /app/startup.sh \
    && chmod +x /app/startup.sh

# Switch to non-root user
USER appuser

# Command to run the ConPort server
ENTRYPOINT ["/app/startup.sh", "python", "-m", "context_portal_mcp.main"]
CMD ["--mode", "http", "--host", "0.0.0.0", "--port", "8000", "--workspace_id", "/app/workspace", "--log-file", "/app/workspace/logs/conport.log", "--log-level", "INFO"]