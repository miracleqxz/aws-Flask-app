FROM python:3.12-slim

WORKDIR /app

# Install curl for healthchecks
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files (filtered by .dockerignore)
COPY . .

RUN chmod +x /app/startup.sh

EXPOSE 5000

CMD ["/app/startup.sh"]
