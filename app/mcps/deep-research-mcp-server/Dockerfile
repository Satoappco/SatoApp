FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy and install open_deep_research library
COPY src/open_deep_research /app/src/open_deep_research
RUN cd /app/src/open_deep_research && pip install --no-cache-dir -e .

# Copy server files
COPY __init__.py .
COPY http_server.py .
COPY research_engine.py .

# Expose port
EXPOSE 8004

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8004/health')"

# Run server
CMD ["python", "http_server.py"]
