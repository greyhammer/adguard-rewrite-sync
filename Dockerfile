# Multi-stage build for improved AdGuard DNS Sync application
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create .kube directory for the user
RUN mkdir -p /home/appuser/.kube && chown -R appuser:appuser /home/appuser

# Create data directory for persistent storage
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

# Copy application code
COPY *.py ./

# Make app executable
RUN chmod +x app.py

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check with improved reliability
HEALTHCHECK --interval=60s --timeout=30s --start-period=30s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8080/health', timeout=10)" || exit 1

# Expose health check port
EXPOSE 8080

# Run the improved application
CMD ["python3", "app.py"]
