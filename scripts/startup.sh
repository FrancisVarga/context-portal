#!/bin/bash
set -e

# Initialize PostgreSQL if needed
if [ ! -f /var/lib/postgresql/*/main/PG_VERSION ]; then
  echo "Initializing PostgreSQL database..."
  sudo -u postgres /usr/lib/postgresql/*/bin/initdb -D /var/lib/postgresql/*/main
fi

# Start PostgreSQL
echo "Starting PostgreSQL..."
sudo -u postgres /usr/lib/postgresql/*/bin/pg_ctl -D /var/lib/postgresql/*/main -l /var/log/postgresql/postgresql.log start

# Wait for PostgreSQL to start
echo "Waiting for PostgreSQL to start..."
while ! sudo -u postgres pg_isready; do
  echo "Still waiting for PostgreSQL..."
  sleep 1
done

# Create database user and database if they don't exist
echo "Setting up database..."
sudo -u postgres psql -c "SELECT 1 FROM pg_user WHERE usename = 'conport';" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER conport WITH SUPERUSER PASSWORD 'conport';" || true

sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw context_portal || \
  sudo -u postgres createdb -O conport context_portal || true

echo "PostgreSQL setup complete."

# Execute the main command
exec "$@"