# PostgreSQL Deployment Guide

This guide will help you deploy the Sato application with PostgreSQL on Google Cloud.

## 🔧 What Changed

- ✅ **Replaced SQLite** with **PostgreSQL** using **SQLModel**
- ✅ **Added connection pooling** for production reliability
- ✅ **Environment-based configuration** for different deployment environments
- ✅ **Health check endpoint** for monitoring database connectivity
- ✅ **Migration script** to transfer existing SQLite data

## 📋 Prerequisites

1. **Google Cloud SQL PostgreSQL 17 instance** (you already have this!)
2. **OpenAI API Key** for CrewAI functionality
3. **Google Cloud CLI** installed and configured

## 🚀 Deployment Steps

### Step 1: Set Up Your PostgreSQL Database

If you haven't already, create a database in your PostgreSQL instance:

```sql
-- Connect to your PostgreSQL instance and run:
CREATE DATABASE sato_db;
CREATE USER sato_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE sato_db TO sato_user;
```

### Step 2: Configure Environment Variables

For Google Cloud Run deployment, set these environment variables:

```bash
# Set environment variables for Cloud Run
gcloud run services update sato-app \
  --set-env-vars \
  OPENAI_API_KEY=your_openai_api_key,\
  API_KEY=your_secure_webhook_key,\
  DB_HOST=your_postgresql_instance_ip,\
  DB_PORT=5432,\
  DB_NAME=sato_db,\
  DB_USER=sato_user,\
  DB_PASSWORD=your_secure_password,\
  GOOGLE_CLOUD_SQL=true
```

**Alternative: Use DATABASE_URL**
```bash
gcloud run services update sato-app \
  --set-env-vars \
  DATABASE_URL=postgresql://sato_user:password@host:5432/sato_db,\
  OPENAI_API_KEY=your_openai_api_key,\
  API_KEY=your_secure_webhook_key
```

### Step 3: Deploy to Google Cloud Run

```bash
# Deploy the updated application
gcloud run deploy sato-app \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300
```

### Step 4: Migrate Existing Data (Optional)

If you have existing SQLite data to migrate:

```bash
# Run locally with PostgreSQL environment variables set
python migrate_to_postgresql.py
```

### Step 5: Verify Deployment

Test the health endpoints:

```bash
# Test webhook health
curl -H "Authorization: Bearer your_secure_webhook_key" \
  https://your-app-url/health

# Test FastAPI health  
curl https://your-app-url/
```

## 🛠️ New Features Added

### Health Check Endpoint
- **URL**: `GET /health`
- **Purpose**: Monitor database connectivity
- **Authentication**: Bearer token required

### Recent Entries Endpoint
- **URL**: `GET /webhook/recent?limit=10`
- **Purpose**: View recent webhook entries for debugging
- **Authentication**: Bearer token required

### Enhanced Error Handling
- Better error messages for database connection issues
- Graceful handling of database failures
- Detailed logging for troubleshooting

## 🔍 Monitoring & Troubleshooting

### Check Database Connection
```bash
curl -H "Authorization: Bearer your_api_key" \
  https://your-app-url/health
```

### View Recent Webhook Entries
```bash
curl -H "Authorization: Bearer your_api_key" \
  https://your-app-url/webhook/recent?limit=5
```

### Check Application Logs
```bash
gcloud run logs read sato-app --region=us-central1
```

## 🔐 Security Best Practices

1. **Use strong passwords** for database users
2. **Set secure API_KEY** (not the default "SatoLogos")
3. **Use Google Cloud Secret Manager** for sensitive data:
   ```bash
   # Store secrets
   gcloud secrets create openai-api-key --data-file=openai_key.txt
   gcloud secrets create db-password --data-file=db_pass.txt
   
   # Update Cloud Run to use secrets
   gcloud run services update sato-app \
     --update-secrets OPENAI_API_KEY=openai-api-key:latest,\
     DB_PASSWORD=db-password:latest
   ```

## 📊 Database Schema

The new PostgreSQL schema:

```sql
CREATE TABLE webhook_entries (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255),
    user_choice VARCHAR(255), 
    raw_payload TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🚨 Migration Notes

- **SQLModel** provides excellent type safety and validation
- **Connection pooling** improves performance and reliability
- **UTC timestamps** for consistent time handling
- **JSON validation** for webhook payloads
- **Graceful error handling** prevents application crashes

## 📈 Performance Benefits

- **Connection pooling**: Reuses database connections
- **Async-ready**: Compatible with FastAPI's async features
- **Type safety**: Prevents runtime errors with Pydantic validation
- **Scalability**: PostgreSQL handles concurrent connections better than SQLite

Your application is now production-ready with PostgreSQL! 🎉
