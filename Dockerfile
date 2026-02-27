FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY bot/ ./bot/

# Data volume for SQLite
RUN mkdir -p /app/data
COPY . .

RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
