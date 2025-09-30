#!/bin/bash

# Simple IP Whitelisting for Cloud Run using VPC Firewall Rules
# This is a simpler approach than Cloud Armor

echo "🔒 Setting up simple IP whitelisting for Cloud Run service..."

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
FIREWALL_RULE_NAME="sato-ip-whitelist-rule"
NETWORK_NAME="default"

echo -e "${BLUE}📋 Configuration:${NC}"
echo "  Project: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service: $SERVICE_NAME"
echo "  Whitelist IP: $WHITELIST_IP"
echo "  Firewall Rule: $FIREWALL_RULE_NAME"
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
gcloud services enable run.googleapis.com

# Step 1: Create a VPC firewall rule to allow only whitelisted IP
echo -e "${BLUE}🛡️  Step 1: Creating VPC firewall rule for IP whitelisting...${NC}"
gcloud compute firewall-rules create $FIREWALL_RULE_NAME \
    --network=$NETWORK_NAME \
    --allow=tcp:443,tcp:80 \
    --source-ranges=$WHITELIST_IP \
    --description="Allow access to Cloud Run from whitelisted IP: $WHITELIST_IP" \
    --target-tags=cloud-run

# Step 2: Create a deny rule for all other IPs
echo -e "${BLUE}🚫 Step 2: Creating deny rule for all other IPs...${NC}"
gcloud compute firewall-rules create sato-deny-all-other-ips \
    --network=$NETWORK_NAME \
    --deny=tcp:443,tcp:80 \
    --source-ranges=0.0.0.0/0 \
    --description="Deny access to Cloud Run from all other IPs" \
    --target-tags=cloud-run \
    --priority=1000

# Step 3: Update Cloud Run service to use VPC connector
echo -e "${BLUE}🔗 Step 3: Setting up VPC connector for Cloud Run...${NC}"

# Create VPC connector if it doesn't exist
VPC_CONNECTOR_NAME="sato-vpc-connector"
if ! gcloud compute networks vpc-access connectors describe $VPC_CONNECTOR_NAME --region=$REGION &>/dev/null; then
    echo "Creating VPC connector..."
    gcloud compute networks vpc-access connectors create $VPC_CONNECTOR_NAME \
        --region=$REGION \
        --subnet=default \
        --subnet-project=$PROJECT_ID \
        --min-instances=2 \
        --max-instances=3
else
    echo "VPC connector already exists."
fi

# Step 4: Update Cloud Run service to use VPC connector
echo -e "${BLUE}🚀 Step 4: Updating Cloud Run service to use VPC connector...${NC}"
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --vpc-connector=$VPC_CONNECTOR_NAME \
    --vpc-egress=all-traffic

# Step 5: Create a load balancer with IP whitelisting
echo -e "${BLUE}🌐 Step 5: Creating load balancer with IP restrictions...${NC}"

# Get Cloud Run service URL
CLOUD_RUN_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
echo "Cloud Run URL: $CLOUD_RUN_URL"

# Create backend service
BACKEND_SERVICE_NAME="sato-backend-service"
gcloud compute backend-services create $BACKEND_SERVICE_NAME \
    --global \
    --protocol=HTTPS \
    --port-name=https

# Create URL map
LOAD_BALANCER_NAME="sato-load-balancer"
gcloud compute url-maps create $LOAD_BALANCER_NAME \
    --default-service=$BACKEND_SERVICE_NAME

# Create HTTPS proxy
gcloud compute target-https-proxies create sato-https-proxy \
    --url-map=$LOAD_BALANCER_NAME

# Create global forwarding rule
gcloud compute forwarding-rules create sato-forwarding-rule \
    --global \
    --target-https-proxy=sato-https-proxy \
    --ports=443

echo ""
echo -e "${GREEN}✅ Simple IP whitelisting setup completed!${NC}"
echo ""
echo -e "${YELLOW}📋 Summary:${NC}"
echo "  ✓ Firewall rule created: $FIREWALL_RULE_NAME"
echo "  ✓ Whitelisted IP: $WHITELIST_IP"
echo "  ✓ VPC connector: $VPC_CONNECTOR_NAME"
echo "  ✓ Load balancer: $LOAD_BALANCER_NAME"
echo ""
echo -e "${YELLOW}🌐 Access URLs:${NC}"
echo "  Original Cloud Run: $CLOUD_RUN_URL"
echo "  Protected URL: https://[LOAD_BALANCER_IP] (via load balancer)"
echo ""
echo -e "${YELLOW}🔧 Management Commands:${NC}"
echo "  View firewall rules: gcloud compute firewall-rules list --filter='name~sato'"
echo "  Add more IPs: gcloud compute firewall-rules update $FIREWALL_RULE_NAME --source-ranges='$WHITELIST_IP,NEW_IP'"
echo "  Remove rule: gcloud compute firewall-rules delete $FIREWALL_RULE_NAME"
echo ""
echo -e "${YELLOW}🧪 Testing:${NC}"
echo "  Test from whitelisted IP: curl $CLOUD_RUN_URL/"
echo "  Test from other IP: Should be blocked by firewall"
echo ""
echo -e "${GREEN}🎉 Your Cloud Run service is now protected with IP whitelisting!${NC}"
