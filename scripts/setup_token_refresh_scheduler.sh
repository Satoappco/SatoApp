#!/bin/bash
# Creates Cloud Scheduler job to trigger token refresh every 30 minutes

set -e

# Get project ID from environment or use default
PROJECT_ID="${PROJECT_ID:-superb-dream-470215-i7}"
# Cloud Scheduler is not available in me-west1, use europe-west1 instead
# This is close geographically and supports Cloud Scheduler
SCHEDULER_REGION="${SCHEDULER_REGION:-europe-west1}"
SERVICE_URL="https://sato-frontend-dev-397762748853.me-west1.run.app/"
SCHEDULER_NAME="token-refresh-30min"

# Load INTERNAL_AUTH_TOKEN from .env file if not set
if [ -z "$INTERNAL_AUTH_TOKEN" ]; then
    # Try current directory first (SatoApp/)
    if [ -f ".env" ]; then
        INTERNAL_AUTH_TOKEN=$(grep "^INTERNAL_AUTH_TOKEN=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    # Try parent directory
    elif [ -f "../.env" ]; then
        INTERNAL_AUTH_TOKEN=$(grep "^INTERNAL_AUTH_TOKEN=" ../.env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    fi
fi

# Check if INTERNAL_AUTH_TOKEN is set
if [ -z "$INTERNAL_AUTH_TOKEN" ]; then
    echo "❌ Error: INTERNAL_AUTH_TOKEN not found"
    echo "Please add it to your .env file or set it with:"
    echo "  export INTERNAL_AUTH_TOKEN='your-secure-token'"
    exit 1
fi

echo "🚀 Setting up Cloud Scheduler for Token Refresh..."
echo "   Project ID: $PROJECT_ID"
echo "   Scheduler Region: $SCHEDULER_REGION"
echo "   Service URL: $SERVICE_URL"
echo "   Schedule: Every 30 minutes"
echo "   Scheduler Name: $SCHEDULER_NAME"
echo ""
echo "📍 Note: Cloud Scheduler region ($SCHEDULER_REGION) can be different from"
echo "   Cloud Run region (me-west1). The scheduler will call your service via HTTPS."
echo ""

# Create or update the scheduler job
echo "📝 Creating Cloud Scheduler job..."

if gcloud scheduler jobs describe $SCHEDULER_NAME --location=$SCHEDULER_REGION --project=$PROJECT_ID &>/dev/null; then
    echo "⚠️  Job already exists. Updating..."
    gcloud scheduler jobs update http $SCHEDULER_NAME \
      --location=$SCHEDULER_REGION \
      --uri="$SERVICE_URL/api/v1/connections/refresh-all" \
      --http-method="POST" \
      --headers="Content-Type=application/json,X-Internal-Auth-Token=${INTERNAL_AUTH_TOKEN}" \
      --attempt-deadline="600s" \
      --description="Token refresh job - runs every 30 minutes to refresh all OAuth tokens"
else
    gcloud scheduler jobs create http $SCHEDULER_NAME \
      --project=$PROJECT_ID \
      --location=$SCHEDULER_REGION \
      --schedule="*/30 * * * *" \
      --time-zone="Asia/Jerusalem" \
      --uri="$SERVICE_URL/api/v1/connections/refresh-all" \
      --http-method="POST" \
      --headers="Content-Type=application/json,X-Internal-Auth-Token=${INTERNAL_AUTH_TOKEN}" \
      --attempt-deadline="600s" \
      --description="Token refresh job - runs every 30 minutes to refresh all OAuth tokens"
fi

echo "✅ Cloud Scheduler job created successfully!"
echo ""
echo "To update the job later, run:"
echo "  gcloud scheduler jobs update http $SCHEDULER_NAME --location=$SCHEDULER_REGION"
echo ""
echo "To delete the job, run:"
echo "  gcloud scheduler jobs delete $SCHEDULER_NAME --location=$SCHEDULER_REGION"
echo ""
echo "To test the endpoint manually:"
echo "  curl -X POST \"$SERVICE_URL/api/v1/connections/refresh-all\" -H \"X-Internal-Auth-Token: $INTERNAL_AUTH_TOKEN\" -H \"Content-Type: application/json\""