#!/bin/bash

# Cloud Armor IP Whitelisting for Cloud Run - Most Effective Approach
# This script creates a Cloud Armor policy and applies it to a load balancer

echo "🛡️  Setting up Cloud Armor IP whitelisting for Cloud Run service..."

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
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Step 1: Create Cloud Armor security policy
echo -e "${BLUE}🛡️  Step 1: Creating Cloud Armor security policy...${NC}"
gcloud compute security-policies create $POLICY_NAME \
    --description="IP whitelist policy for Sato Cloud Run service - Allow only $WHITELIST_IP" \
    --global

# Step 2: Add whitelist rule (higher priority)
echo -e "${BLUE}✅ Step 2: Adding whitelist rule for $WHITELIST_IP...${NC}"
gcloud compute security-policies rules create 1000 \
    --security-policy=$POLICY_NAME \
    --expression="origin.ip in ['$WHITELIST_IP']" \
    --action=allow \
    --description="Allow whitelisted IP: $WHITELIST_IP" \
    --preview

# Step 3: Add deny rule for all other IPs (lower priority)
echo -e "${BLUE}🚫 Step 3: Adding deny rule for all other IPs...${NC}"
gcloud compute security-policies rules create 2000 \
    --security-policy=$POLICY_NAME \
    --expression="true" \
    --action=deny-403 \
    --description="Deny all other IPs"

# Step 4: Get Cloud Run service details
echo -e "${BLUE}🌐 Step 4: Getting Cloud Run service details...${NC}"
CLOUD_RUN_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
if [ -z "$CLOUD_RUN_URL" ]; then
    echo -e "${RED}❌ Error: Could not get Cloud Run service URL. Make sure the service exists.${NC}"
    echo "Available services:"
    gcloud run services list --region=$REGION
    exit 1
fi

echo "Cloud Run URL: $CLOUD_RUN_URL"

# Step 5: Create a serverless NEG (Network Endpoint Group) for Cloud Run
echo -e "${BLUE}🔗 Step 5: Creating serverless NEG for Cloud Run...${NC}"
NEG_NAME="sato-cloud-run-neg"
gcloud compute network-endpoint-groups create $NEG_NAME \
    --region=$REGION \
    --network-endpoint-type=serverless \
    --cloud-run-service=$SERVICE_NAME

# Step 6: Create backend service
echo -e "${BLUE}🔧 Step 6: Creating backend service...${NC}"
BACKEND_SERVICE_NAME="sato-backend-service"
gcloud compute backend-services create $BACKEND_SERVICE_NAME \
    --global \
    --protocol=HTTPS \
    --port-name=https

# Add the NEG as backend
echo -e "${BLUE}🔗 Adding NEG as backend...${NC}"
gcloud compute backend-services add-backend $BACKEND_SERVICE_NAME \
    --global \
    --network-endpoint-group=$NEG_NAME \
    --network-endpoint-group-region=$REGION

# Step 7: Apply Cloud Armor policy to backend service
echo -e "${BLUE}🛡️  Step 7: Applying Cloud Armor policy to backend service...${NC}"
gcloud compute backend-services update $BACKEND_SERVICE_NAME \
    --global \
    --security-policy=$POLICY_NAME

# Step 8: Create URL map
echo -e "${BLUE}🗺️  Step 8: Creating URL map...${NC}"
LOAD_BALANCER_NAME="sato-load-balancer"
gcloud compute url-maps create $LOAD_BALANCER_NAME \
    --default-service=$BACKEND_SERVICE_NAME

# Step 9: Create HTTPS proxy
echo -e "${BLUE}🔐 Step 9: Creating HTTPS proxy...${NC}"
gcloud compute target-https-proxies create sato-https-proxy \
    --url-map=$LOAD_BALANCER_NAME

# Step 10: Create global forwarding rule
echo -e "${BLUE}🌍 Step 10: Creating global forwarding rule...${NC}"
gcloud compute forwarding-rules create sato-forwarding-rule \
    --global \
    --target-https-proxy=sato-https-proxy \
    --ports=443

# Get the load balancer IP
echo -e "${BLUE}🔍 Getting load balancer IP address...${NC}"
LB_IP=$(gcloud compute forwarding-rules describe sato-forwarding-rule --global --format="value(IPAddress)")
echo "Load Balancer IP: $LB_IP"

echo ""
echo -e "${GREEN}✅ Cloud Armor IP whitelisting setup completed successfully!${NC}"
echo ""
echo -e "${YELLOW}📋 Summary:${NC}"
echo "  ✓ Cloud Armor policy: $POLICY_NAME"
echo "  ✓ Whitelisted IP: $WHITELIST_IP"
echo "  ✓ Backend service: $BACKEND_SERVICE_NAME"
echo "  ✓ Load balancer: $LOAD_BALANCER_NAME"
echo "  ✓ Load balancer IP: $LB_IP"
echo ""
echo -e "${YELLOW}🌐 Access URLs:${NC}"
echo "  Original Cloud Run: $CLOUD_RUN_URL"
echo "  Protected URL: https://$LB_IP (via load balancer with IP whitelisting)"
echo ""
echo -e "${YELLOW}🔧 Management Commands:${NC}"
echo "  View policy: gcloud compute security-policies describe $POLICY_NAME"
echo "  List rules: gcloud compute security-policies rules list --security-policy=$POLICY_NAME"
echo "  Add more IPs: gcloud compute security-policies rules create 1001 --security-policy=$POLICY_NAME --expression=\"origin.ip in ['NEW_IP']\" --action=allow"
echo "  Remove policy: gcloud compute security-policies delete $POLICY_NAME"
echo ""
echo -e "${YELLOW}🧪 Testing:${NC}"
echo "  Test from whitelisted IP ($WHITELIST_IP):"
echo "    curl https://$LB_IP/"
echo "  Test from other IP: Should return 403 Forbidden"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "  1. Update your DNS to point to the load balancer IP: $LB_IP"
echo "  2. Test access from the whitelisted IP"
echo "  3. Verify that other IPs are blocked"
echo ""
echo -e "${GREEN}🎉 Your Cloud Run service is now protected with Cloud Armor IP whitelisting!${NC}"
