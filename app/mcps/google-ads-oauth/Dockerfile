FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY google-ads-oauth/requirements-http.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-http.txt

# Copy Google Ads MCP source
COPY google_ads_mcp /app/google_ads_mcp

# Copy HTTP server files
COPY google-ads-oauth/http_server.py .

# Expose port for HTTP server
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8002/health', timeout=5.0)" || exit 1

# Run HTTP server
CMD ["python", "http_server.py"]
