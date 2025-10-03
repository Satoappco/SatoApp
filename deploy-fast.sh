#!/bin/bash

# Fast Sato Backend Deployment Script
# Optimized for speed with minimal overhead

echo "🚀 Deploying Sato AI Backend to Google Cloud Run..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
REGION="me-west1"
SERVICE_NAME="sato-backend-v2"
PROJECT_ID=$(gcloud config get-value project)
CLOUD_SQL_INSTANCE="sato-db"  # Correct Cloud SQL instance name

echo -e "${BLUE}📋 Fast Deployment Configuration:${NC}"
echo "  Service: $SERVICE_NAME"
echo "  Region: $REGION"
echo "  Project: $PROJECT_ID"
echo "  Cloud SQL: $CLOUD_SQL_INSTANCE"
echo "  Memory: 8Gi (optimized for AI workloads)"
echo "  CPU: 4 (enhanced parallel processing)"
echo "  Timeout: 900s (15 min for AI tasks)"
echo "  Concurrency: 2 (optimized for AI performance)"
echo ""

# Load environment variables from .env file
echo -e "${BLUE}📄 Loading environment variables from .env file...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ ERROR: .env file not found!${NC}"
    echo "Please create a .env file with required environment variables."
    exit 1
fi

# Convert .env to YAML format for Cloud Run with production URLs
echo -e "${BLUE}🔄 Converting .env to Cloud Run YAML format with production URLs...${NC}"
python3 << 'PYTHON_SCRIPT'
import os
import re
import sys

def parse_env_line(line):
    """Parse a single line from .env file"""
    line = line.strip()
    
    # Skip comments and empty lines
    if not line or line.startswith('#'):
        return None, None
    
    # Must have = sign
    if '=' not in line:
        return None, None
    
    # Split on first = only
    key, value = line.split('=', 1)
    key = key.strip()
    value = value.strip()
    
    # Remove surrounding quotes if present
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    
    return key, value

# Read .env file
try:
    with open('.env', 'r', encoding='utf-8') as f:
        lines = f.readlines()
except FileNotFoundError:
    print("ERROR: .env file not found!", file=sys.stderr)
    sys.exit(1)

# Parse all environment variables and convert localhost to production URLs
env_vars = {}
for line in lines:
    key, value = parse_env_line(line)
    if key and value:
        # Skip placeholder values
        if value.startswith('your-') or value.startswith('your_'):
            continue
        
        # Convert localhost URLs to production URLs
        if 'localhost:8000' in value:
            value = value.replace('localhost:8000', 'https://sato-backend-v2-397762748853.me-west1.run.app')
        elif 'localhost:3000' in value:
            value = value.replace('localhost:3000', 'https://satoapp.co')
        elif value == 'wss://localhost:8000':
            value = 'wss://sato-backend-v2-397762748853.me-west1.run.app'
        elif value == 'https://localhost:8000':
            value = 'https://sato-backend-v2-397762748853.me-west1.run.app'
        elif value == 'https://localhost:3000':
            value = 'https://satoapp.co'
        
        env_vars[key] = value

# Write YAML file for Cloud Run
with open('.env.cloudrun.yaml', 'w', encoding='utf-8') as f:
    for key, value in env_vars.items():
        # For YAML, we need to properly escape the value
        if '\n' in value or '"' in value:
            # Use literal block scalar for complex values
            f.write(f'{key}: |-\n')
            for line in value.split('\n'):
                f.write(f'  {line}\n')
        else:
            # Simple quoted value
            f.write(f'{key}: "{value}"\n')

print(f"✅ Converted {len(env_vars)} environment variables to YAML format with production URLs")
PYTHON_SCRIPT

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ ERROR: Failed to convert .env to YAML format!${NC}"
    exit 1
fi

# Validate required environment variables
echo -e "${BLUE}🔍 Validating required environment variables...${NC}"
REQUIRED_VARS=("GEMINI_API_KEY" "API_TOKEN" "DATABASE_URL" "DB_PASSWORD")
MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}:" .env.cloudrun.yaml; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo -e "${RED}❌ ERROR: Missing required environment variables:${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo -e "${RED}  - $var${NC}"
    done
    echo ""
    echo "Please fill in these variables in your .env file with actual values"
    rm -f .env.cloudrun.yaml
    exit 1
fi

echo -e "${GREEN}✅ Environment variables loaded and validated with production URLs${NC}"
echo ""

# Deploy with optimized settings using YAML file with production URLs
echo -e "${BLUE}🚀 Deploying with optimized settings...${NC}"
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --memory 8Gi \
  --cpu 4 \
  --timeout 900 \
  --concurrency 2 \
  --max-instances 3 \
  --min-instances 0 \
  --execution-environment gen2 \
  --cpu-boost \
  --add-cloudsql-instances $PROJECT_ID:$REGION:$CLOUD_SQL_INSTANCE \
  --env-vars-file .env.cloudrun.yaml

# Clean up temporary YAML file
rm -f .env.cloudrun.yaml

# Check deployment result
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Fast deployment completed successfully!${NC}"
    
    # Get service URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
    
    echo ""
    echo -e "${GREEN}🌐 Service URL: $SERVICE_URL${NC}"
    echo ""
    echo "🔗 Quick test:"
    echo "  curl $SERVICE_URL/"
    echo ""
    echo "⚡ Backend features deployed:"
    echo "  ✓ 8x Memory (8Gi - optimized for AI)"
    echo "  ✓ 4x CPU (4 cores - enhanced processing)"  
    echo "  ✓ 3x Timeout (900s vs 300s)"
    echo "  ✓ Optimized concurrency (2 for AI performance)"
    echo "  ✓ Auto-scaling (0-3 instances)"
    echo "  ✓ Gen2 execution environment"
    echo "  ✓ CPU boost enabled"
    echo "  ✓ Cloud SQL PostgreSQL connected"
    echo "  ✓ DialogCX webhook endpoints ready"
    echo "  ✓ CrewAI research capabilities enabled"
    echo "  ✓ Chat API with session management"
else
    echo ""
    echo -e "${RED}❌ Fast deployment failed!${NC}"
    echo "Check the error messages above."
    exit 1
fi
