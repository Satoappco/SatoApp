#!/bin/bash

# Sato AI Backend Dor Environment Deployment Script
# Deploys to a separate development service for Dor's testing

echo "🚀 Deploying Sato AI Backend to Google Cloud Run (DOR ENVIRONMENT)..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration for DOR ENVIRONMENT
REGION="me-west1"
SERVICE_NAME="sato-backend-dor"  # Dor's service name
PROJECT_ID=$(gcloud config get-value project)
CLOUD_SQL_INSTANCE="sato-db"  # Same instance, same dev database
DEV_DATABASE_NAME="sato_dev"  # Same dev database as dev environment

# Ensure we're using the correct region
echo -e "${BLUE}🔍 Verifying region configuration...${NC}"
CURRENT_REGION=$(gcloud config get-value run/region 2>/dev/null || echo "unset")
if [ "$CURRENT_REGION" != "$REGION" ]; then
    echo -e "${YELLOW}⚠️  Setting default region to $REGION...${NC}"
    gcloud config set run/region $REGION
fi

echo -e "${BLUE}📋 Dor Environment Deployment Configuration:${NC}"
echo "  Service: $SERVICE_NAME (DOR ENVIRONMENT)"
echo "  Region: $REGION"
echo "  Project: $PROJECT_ID"
echo "  Cloud SQL: $CLOUD_SQL_INSTANCE (shared with dev/prod)"
echo "  Database: $DEV_DATABASE_NAME (same as dev environment)"
echo "  Memory: 4Gi (same as dev)"
echo "  CPU: 2 (same as dev)"
echo "  Timeout: 600s (10 min same as dev)"
echo "  Concurrency: 5 (same as dev)"
echo ""

# Load environment variables from .env file
echo -e "${BLUE}📄 Loading environment variables from .env file...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ ERROR: .env file not found!${NC}"
    echo "Please create a .env file with required environment variables."
    exit 1
fi

# Convert .env to YAML format for Cloud Run with Dor URLs
echo -e "${BLUE}🔄 Converting .env to Cloud Run YAML format with Dor URLs...${NC}"
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

# Parse all environment variables and convert to Dor URLs
env_vars = {}
for line in lines:
    key, value = parse_env_line(line)
    if key and value:
        # Skip placeholder values
        if value.startswith('your-') or value.startswith('your_'):
            continue
        
        # Convert URLs to Dor environment URLs
        # Handle wss:// protocol first
        if value.startswith('wss://sato-backend-v2-397762748853.me-west1.run.app'):
            value = value.replace('wss://sato-backend-v2-397762748853.me-west1.run.app', 'wss://sato-backend-dor-397762748853.me-west1.run.app')
        elif value.startswith('wss://sato-backend-dev-397762748853.me-west1.run.app'):
            value = value.replace('wss://sato-backend-dev-397762748853.me-west1.run.app', 'wss://sato-backend-dor-397762748853.me-west1.run.app')
        # Handle https:// protocols
        elif 'sato-backend-v2-397762748853.me-west1.run.app' in value:
            value = value.replace('sato-backend-v2-397762748853.me-west1.run.app', 'sato-backend-dor-397762748853.me-west1.run.app')
        elif 'sato-backend-dev-397762748853.me-west1.run.app' in value:
            value = value.replace('sato-backend-dev-397762748853.me-west1.run.app', 'sato-backend-dor-397762748853.me-west1.run.app')
        elif 'sato-frontend-397762748853.me-west1.run.app' in value:
            value = value.replace('sato-frontend-397762748853.me-west1.run.app', 'sato-frontend-dor-397762748853.me-west1.run.app')
        elif 'sato-frontend-dev-397762748853.me-west1.run.app' in value:
            value = value.replace('sato-frontend-dev-397762748853.me-west1.run.app', 'sato-frontend-dor-397762748853.me-west1.run.app')
        # Convert production database to development database (same as dev)
        elif 'postgresql://postgres:SatoDB_92vN!fG7kAq4hRzLwYx2!PmE@34.165.111.32:5432/sato' in value:
            value = value.replace('postgresql://postgres:SatoDB_92vN!fG7kAq4hRzLwYx2!PmE@34.165.111.32:5432/sato', 'postgresql://sato_dev_user:SatoDev_92vN!fG7kAq4hRzLwYx2!PmE@34.165.111.32:5432/sato_dev')
        elif 'DB_NAME=sato' in value:
            value = value.replace('DB_NAME=sato', 'DB_NAME=sato_dev')
        elif 'DB_USER=postgres' in value:
            value = value.replace('DB_USER=postgres', 'DB_USER=sato_dev_user')
        # Handle localhost URLs (keep as localhost for dev)
        elif 'localhost:8000' in value:
            # Keep localhost for development
            pass
        elif 'localhost:3000' in value:
            # Keep localhost for development
            pass
        
        env_vars[key] = value

# Write YAML file for Cloud Run
with open('.env.dor.cloudrun.yaml', 'w', encoding='utf-8') as f:
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

print(f"✅ Converted {len(env_vars)} environment variables to YAML format with Dor URLs")
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
    if ! grep -q "^${var}:" .env.dor.cloudrun.yaml; then
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
    rm -f .env.dor.cloudrun.yaml
    exit 1
fi

echo -e "${GREEN}✅ Environment variables loaded and validated with Dor URLs${NC}"
echo ""

# Build image with no cache and deploy
echo -e "${BLUE}🚀 Building Docker image for Dor environment (clean build, no cache)...${NC}"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

# Build image without cache
gcloud builds submit --tag $IMAGE_NAME 
#--no-cache

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker build failed!${NC}"
    rm -f .env.dor.cloudrun.yaml
    exit 1
fi

# Verify YAML file still exists
if [ ! -f ".env.dor.cloudrun.yaml" ]; then
    echo -e "${RED}❌ ERROR: .env.dor.cloudrun.yaml file not found after build!${NC}"
    exit 1
fi

echo -e "${BLUE}🚀 Deploying to Cloud Run with Dor environment settings...${NC}"
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --region=$REGION \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 600 \
  --concurrency 5 \
  --max-instances 2 \
  --min-instances 0 \
  --execution-environment gen2 \
  --cpu-boost \
  --add-cloudsql-instances $PROJECT_ID:$REGION:$CLOUD_SQL_INSTANCE \
  --env-vars-file .env.dor.cloudrun.yaml

# Capture deployment result before cleanup
DEPLOY_RESULT=$?

# Clean up temporary YAML file
rm -f .env.dor.cloudrun.yaml

# Check deployment result
if [ $DEPLOY_RESULT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Dor environment deployment completed successfully!${NC}"
    
    # Get service URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
    
    echo ""
    echo -e "${GREEN}🌐 Dor Backend Service URL: $SERVICE_URL${NC}"
    echo ""
    echo "🔗 Quick test:"
    echo "  curl $SERVICE_URL/"
    echo ""
    echo -e "${YELLOW}⚠️  DOR ENVIRONMENT FEATURES:${NC}"
    echo "  ✓ 4Gi Memory (same as dev environment)"
    echo "  ✓ 2 CPU cores (same as dev environment)"
    echo "  ✓ 10min timeout (same as dev environment)"
    echo "  ✓ Concurrency 5 (same as dev environment)"
    echo "  ✓ Max 2 instances (same as dev environment)"
    echo "  ✓ Shared database with dev environment (sato_dev)"
    echo "  ✓ Dor service name: $SERVICE_NAME"
    echo ""
    echo -e "${BLUE}📝 Next steps:${NC}"
    echo "1. Deploy frontend with: cd ../satoapp-front && ./deploy-dor.sh"
    echo "2. Test Dor's environment independently"
    echo "3. Dor can develop without affecting dev/prod environments"
else
    echo ""
    echo -e "${RED}❌ Dor environment deployment failed!${NC}"
    echo "Check the error messages above."
    exit 1
fi
