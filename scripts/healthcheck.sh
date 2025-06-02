#!/bin/bash
set -e

# Check if PostgreSQL is running and accepting connections
echo "Checking PostgreSQL health..."
if sudo -u postgres pg_isready; then
  echo "PostgreSQL is healthy"
else
  echo "PostgreSQL is not responding"
  exit 1
fi

# Check if the ConPort MCP server is responding (if running in HTTP mode)
if [ -n "$CONPORT_HTTP_PORT" ] || [[ "$*" == *"--mode http"* ]] || [[ "$*" == *"--port"* ]]; then
  # Extract port from arguments or use default
  PORT=8000
  if [[ "$*" == *"--port"* ]]; then
    PORT=$(echo "$*" | sed -n 's/.*--port \([0-9]*\).*/\1/p')
  fi
  
  echo "Checking ConPort MCP server health on port $PORT..."
  # Try to connect to the root endpoint instead of /health
  if curl -f -s "http://localhost:$PORT/" > /dev/null 2>&1; then
    echo "ConPort MCP server is healthy"
  else
    echo "ConPort MCP server is not responding on port $PORT"
    exit 1
  fi
fi

echo "All health checks passed"
exit 0