# 1. Use a lightweight official Python image
FROM python:3.11-slim

# 2. Set working directory inside the container
WORKDIR /app

# 3. Install system dependencies (optional, useful for some Python libs)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# 4. Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your app’s code into the image
COPY . .

# 6. Tell Cloud Run which port to use (default 8080)
ENV PORT=8080

# 7. Start the app with Gunicorn + Uvicorn workers
# 'server:app' means: import server.py and look for 'app' inside it
CMD exec gunicorn -k uvicorn.workers.UvicornWorker --bind :$PORT --workers 1 --threads 8 --timeout 0 server:app
