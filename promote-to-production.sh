#!/bin/bash

# Sato AI Backend Production Promotion Script
# Promotes development changes to production environment

echo "🚀 Promoting Sato AI Backend from Development to Production..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
REGION="me-west1"
DEV_SERVICE_NAME="sato-backend-dev"
PROD_SERVICE_NAME="sato-backend-v2"
PROJECT_ID=$(gcloud config get-value project)
CLOUD_SQL_INSTANCE="sato-db"

echo -e "${BLUE}📋 Production Promotion Configuration:${NC}"
echo "  Development Service: $DEV_SERVICE_NAME"
echo "  Production Service: $PROD_SERVICE_NAME"
echo "  Region: $REGION"
echo "  Project: $PROJECT_ID"
echo "  Cloud SQL: $CLOUD_SQL_INSTANCE"
echo ""

# Safety check - confirm promotion
echo -e "${YELLOW}⚠️  WARNING: This will update your PRODUCTION environment!${NC}"
echo "  - Development service: $DEV_SERVICE_NAME"
echo "  - Production service: $PROD_SERVICE_NAME"
echo "  - This action will affect your QA environment"
echo ""
read -p "Are you sure you want to promote development to production? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "❌ Promotion cancelled."
    exit 1
fi

# Get the current development service image
echo -e "${BLUE}🔍 Getting development service image...${NC}"
DEV_IMAGE=$(gcloud run services describe $DEV_SERVICE_NAME --region=$REGION --format="value(spec.template.spec.template.spec.containers[0].image)")

if [ -z "$DEV_IMAGE" ]; then
    echo -e "${RED}❌ ERROR: Could not get development service image!${NC}"
    echo "Make sure the development service exists and is deployed."
    exit 1
fi

echo "✅ Development image: $DEV_IMAGE"

# Load environment variables from .env file for production
echo -e "${BLUE}📄 Loading environment variables for production...${NC}"
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
        # Handle wss:// protocol first
        if value.startswith('wss://localhost:8000') or value == 'wss://localhost:8000':
            value = value.replace('wss://localhost:8000', 'wss://sato-backend-v2-397762748853.me-west1.run.app')
        # Handle https:// and https:// protocols
        elif 'https://localhost:8000' in value or 'https://localhost:8000' in value:
            value = value.replace('https://localhost:8000', 'sato-backend-v2-397762748853.me-west1.run.app')
            value = value.replace('https://localhost:8000', 'sato-backend-v2-397762748853.me-west1.run.app')
        elif 'https://localhost:3000' in value or 'https://localhost:3000' in value:
            value = value.replace('https://localhost:3000', 'sato-frontend-397762748853.me-west1.run.app')
            value = value.replace('https://localhost:3000', 'sato-frontend-397762748853.me-west1.run.app')
        # Handle bare localhost references
        elif 'localhost:8000' in value:
            value = value.replace('localhost:8000', 'sato-backend-v2-397762748853.me-west1.run.app')
        elif 'localhost:3000' in value:
            value = value.replace('localhost:3000', 'sato-frontend-397762748853.me-west1.run.app')
        # Convert development URLs to production URLs
        elif 'sato-backend-dev-397762748853.me-west1.run.app' in value:
            value = value.replace('sato-backend-dev-397762748853.me-west1.run.app', 'sato-backend-v2-397762748853.me-west1.run.app')
        elif 'sato-frontend-dev-397762748853.me-west1.run.app' in value:
            value = value.replace('sato-frontend-dev-397762748853.me-west1.run.app', 'sato-frontend-397762748853.me-west1.run.app')
        
        env_vars[key] = value

# Write YAML file for Cloud Run
with open('.env.prod.cloudrun.yaml', 'w', encoding='utf-8') as f:
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
    if ! grep -q "^${var}:" .env.prod.cloudrun.yaml; then
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
    rm -f .env.prod.cloudrun.yaml
    exit 1
fi

echo -e "${GREEN}✅ Environment variables loaded and validated with production URLs${NC}"
echo ""

# Deploy to production using the development image
echo -e "${BLUE}🚀 Deploying to production with development image...${NC}"
gcloud run deploy $PROD_SERVICE_NAME \
  --image $DEV_IMAGE \
  --region=$REGION \
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
  --env-vars-file .env.prod.cloudrun.yaml

# Capture deployment result before cleanup
DEPLOY_RESULT=$?

# Clean up temporary YAML file
rm -f .env.prod.cloudrun.yaml

# Check deployment result
if [ $DEPLOY_RESULT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Production promotion completed successfully!${NC}"
    
    # Get service URL
    PROD_SERVICE_URL=$(gcloud run services describe $PROD_SERVICE_NAME --region=$REGION --format="value(status.url)")
    
    echo ""
    echo -e "${GREEN}🌐 Production Service URL: $PROD_SERVICE_URL${NC}"
    echo ""
    echo "🔗 Quick test:"
    echo "  curl $PROD_SERVICE_URL/"
    echo ""
    echo -e "${GREEN}✅ PRODUCTION FEATURES PROMOTED:${NC}"
    echo "  ✓ 8Gi Memory (production optimized for AI)"
    echo "  ✓ 4 CPU cores (production enhanced processing)"
    echo "  ✓ 15min timeout (production AI tasks)"
    echo "  ✓ Optimized concurrency (2 for AI performance)"
    echo "  ✓ Auto-scaling (0-3 instances)"
    echo "  ✓ Gen2 execution environment"
    echo "  ✓ CPU boost enabled"
    echo "  ✓ Cloud SQL PostgreSQL connected"
    echo "  ✓ DialogCX webhook endpoints ready"
    echo "  ✓ CrewAI research capabilities enabled"
    echo "  ✓ Chat API with session management"
    echo ""
    echo -e "${YELLOW}📝 Next steps:${NC}"
    echo "1. Test your production environment"
    echo "2. Your QA team can now test the updated production"
    echo "3. Development environment remains available for further changes"
    echo "4. Use ./deploy-dev.sh to make more development changes"
else
    echo ""
    echo -e "${RED}❌ Production promotion failed!${NC}"
    echo "Check the error messages above."
    exit 1
fi
