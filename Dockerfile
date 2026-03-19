# Use lightweight Python
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Avoid buffering (important for logs)
ENV PYTHONUNBUFFERED=1

# Install system deps (only if needed)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port
EXPOSE 8000

# Run FastAPI (production ready)
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "fastapibackend:app", "--bind", "0.0.0.0:8000"]