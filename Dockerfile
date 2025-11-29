FROM python:3.12-slim

LABEL org.opencontainers.image.source=https://github.com/miracleqxz/k8s-Flask-app
LABEL org.opencontainers.image.description="Movie Database Flask Application"

WORKDIR /app


RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .


EXPOSE 5000


HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1


CMD ["python", "app.py"]