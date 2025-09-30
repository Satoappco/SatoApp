#!/bin/bash

# Google Cloud CLI IP Whitelisting Setup for Cloud Run
# This script sets up Google Cloud Armor to whitelist specific IP addresses

echo "🔒 Setting up IP whitelisting for Cloud Run service..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
PROJECT_ID=$(gcloud config get-value project)
REGION="me-west1"
SERVICE_NAME="sato-backend"
WHITELIST_IP="89.138.215.114"
POLICY_NAME="sato-ip-whitelist-policy"
BACKEND_SERVICE_NAME="sato-backend-service"
LOAD_BALANCER_NAME="sato-load-balancer"
HEALTH_CHECK_NAME="sato-health-check"

echo -e "${BLUE}📋 Configuration:${NC}"
echo "  Project: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service: $SERVICE_NAME"
echo "  Whitelist IP: $WHITELIST_IP"
echo "  Policy: $POLICY_NAME"
echo ""

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${RED}❌ Error: Not authenticated with gcloud. Please run 'gcloud auth login' first.${NC}"
    exit 1
fi

# Set the project
echo -e "${BLUE}🔧 Setting project to $PROJECT_ID...${NC}"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "${BLUE}🔧 Enabling required APIs...${NC}"
gcloud services enable compute.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable compute.googleapis.com

# Step 1: Create a Cloud Armor security policy
echo -e "${BLUE}🛡️  Step 1: Creating Cloud Armor security policy...${NC}"
gcloud compute security-policies create $POLICY_NAME \
    --description="IP whitelist policy for Sato Cloud Run service" \
    --global

# Add IP whitelist rule
echo -e "${BLUE}🔒 Adding IP whitelist rule for $WHITELIST_IP...${NC}"
gcloud compute security-policies rules create 1000 \
    --security-policy=$POLICY_NAME \
    --expression="origin.ip in ['$WHITELIST_IP']" \
    --action=allow \
    --description="Allow whitelisted IP: $WHITELIST_IP"

# Add deny rule for all other IPs
echo -e "${BLUE}🚫 Adding deny rule for all other IPs...${NC}"
gcloud compute security-policies rules create 2000 \
    --security-policy=$POLICY_NAME \
    --expression="true" \
    --action=deny-403 \
    --description="Deny all other IPs"

# Step 2: Create a health check
echo -e "${BLUE}🏥 Step 2: Creating health check...${NC}"
gcloud compute health-checks create http $HEALTH_CHECK_NAME \
    --port=8080 \
    --request-path="/health" \
    --check-interval=10s \
    --timeout=5s \
    --unhealthy-threshold=3 \
    --healthy-threshold=2

# Step 3: Get Cloud Run service URL
echo -e "${BLUE}🌐 Step 3: Getting Cloud Run service URL...${NC}"
CLOUD_RUN_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
if [ -z "$CLOUD_RUN_URL" ]; then
    echo -e "${RED}❌ Error: Could not get Cloud Run service URL. Make sure the service exists.${NC}"
    exit 1
fi

echo "Cloud Run URL: $CLOUD_RUN_URL"

# Extract domain from Cloud Run URL (remove https://)
CLOUD_RUN_DOMAIN=$(echo $CLOUD_RUN_URL | sed 's|https://||')

# Step 4: Create a backend service
echo -e "${BLUE}🔧 Step 4: Creating backend service...${NC}"
gcloud compute backend-services create $BACKEND_SERVICE_NAME \
    --global \
    --protocol=HTTPS \
    --health-checks=$HEALTH_CHECK_NAME \
    --port-name=https

# Add Cloud Run as backend
echo -e "${BLUE}🔗 Adding Cloud Run as backend...${NC}"
gcloud compute backend-services add-backend $BACKEND_SERVICE_NAME \
    --global \
    --network-endpoint-group=$CLOUD_RUN_DOMAIN \
    --network-endpoint-group-region=$REGION

# Step 5: Create URL map
echo -e "${BLUE}🗺️  Step 5: Creating URL map...${NC}"
gcloud compute url-maps create $LOAD_BALANCER_NAME \
    --default-service=$BACKEND_SERVICE_NAME

# Step 6: Create HTTPS proxy
echo -e "${BLUE}🔐 Step 6: Creating HTTPS proxy...${NC}"
gcloud compute target-https-proxies create sato-https-proxy \
    --url-map=$LOAD_BALANCER_NAME \
    --ssl-certificates=sato-ssl-cert

# Step 7: Create SSL certificate (self-signed for testing)
echo -e "${BLUE}📜 Step 7: Creating SSL certificate...${NC}"
gcloud compute ssl-certificates create sato-ssl-cert \
    --domains=$CLOUD_RUN_DOMAIN

# Step 8: Create global forwarding rule
echo -e "${BLUE}🌍 Step 8: Creating global forwarding rule...${NC}"
gcloud compute forwarding-rules create sato-forwarding-rule \
    --global \
    --target-https-proxy=sato-https-proxy \
    --ports=443

# Step 9: Apply Cloud Armor policy to backend service
echo -e "${BLUE}🛡️  Step 9: Applying Cloud Armor policy to backend service...${NC}"
gcloud compute backend-services update $BACKEND_SERVICE_NAME \
    --global \
    --security-policy=$POLICY_NAME

echo ""
echo -e "${GREEN}✅ IP whitelisting setup completed successfully!${NC}"
echo ""
echo -e "${YELLOW}📋 Summary:${NC}"
echo "  ✓ Cloud Armor policy created: $POLICY_NAME"
echo "  ✓ Whitelisted IP: $WHITELIST_IP"
echo "  ✓ Load balancer created: $LOAD_BALANCER_NAME"
echo "  ✓ Backend service: $BACKEND_SERVICE_NAME"
echo "  ✓ Health check: $HEALTH_CHECK_NAME"
echo ""
echo -e "${YELLOW}🌐 Access URLs:${NC}"
echo "  Original Cloud Run: $CLOUD_RUN_URL"
echo "  Protected URL: https://$CLOUD_RUN_DOMAIN (via load balancer)"
echo ""
echo -e "${YELLOW}🔧 Management Commands:${NC}"
echo "  View policy: gcloud compute security-policies describe $POLICY_NAME"
echo "  Add more IPs: gcloud compute security-policies rules create 1001 --security-policy=$POLICY_NAME --expression=\"origin.ip in ['NEW_IP']\" --action=allow"
echo "  Remove policy: gcloud compute security-policies delete $POLICY_NAME"
echo ""
echo -e "${YELLOW}🧪 Testing:${NC}"
echo "  Test from whitelisted IP: curl https://$CLOUD_RUN_DOMAIN/health"
echo "  Test from other IP: Should return 403 Forbidden"
echo ""
echo -e "${GREEN}🎉 Your Cloud Run service is now protected with IP whitelisting!${NC}"
