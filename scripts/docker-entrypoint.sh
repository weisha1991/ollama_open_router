#!/usr/bin/env bash
set -e

# Fix permissions for mounted volumes (run as root initially)
if [ "$(id -u)" = "0" ]; then
    # Ensure directories exist and have correct permissions
    mkdir -p /app/logs /app/state
    chown -R ollama:ollama /app/logs /app/state

    # Switch to ollama user and re-execute
    exec gosu ollama "$@"
fi

# Execute the main command (running as ollama user)
exec "$@"
