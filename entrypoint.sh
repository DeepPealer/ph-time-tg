#!/bin/bash
set -e

# Wait for DB to be ready
echo "Waiting for PostgreSQL..."
# Using a simple check if the port is open
while ! exec 6<>/dev/tcp/db/5432; do
    sleep 1
done
exec 6>&-

echo "PostgreSQL is up - executing migrations"
# Run migrations
alembic upgrade head

echo "Starting Bot..."
exec python -m bot.main
