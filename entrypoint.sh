#!/bin/sh
set -e

# Wait for DB to be ready
echo "Waiting for PostgreSQL..."
# Using python to check DB connection since it's already installed
python << END
import socket
import time
import os

db_host = "db"
db_port = 5432

while True:
    try:
        with socket.create_connection((db_host, db_port), timeout=1):
            break
    except (OSError, ConnectionRefusedError):
        print("PostgreSQL is not ready yet, sleeping...")
        time.sleep(1)
END

echo "PostgreSQL is up - executing migrations"
# Run migrations
alembic upgrade head

echo "Starting Bot..."
exec python -m bot.main
