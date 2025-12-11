#!/bin/bash
# Creates Cloud Scheduler job to trigger campaign sync daily at 2 AM (DEVELOPMENT)

set -e

# Configuration for DEVELOPMENT
PROJECT_ID="${PROJECT_ID:-superb-dream-470215-i7}"
REGION="${REGION:-europe-west3}"  # Cloud Scheduler doesn't support me-west1, using europe-west3 (Brussels)
SCHEDULER_LOCATION="${SCHEDULER_LOCATION:-europe-west3}"
SERVICE_URL="https://sato-backend-dev-397762748853.me-west1.run.app"
SCHEDULER_NAME="campaign-sync-daily-dev"

echo "🚀 Setting up Cloud Scheduler for Campaign Sync (DEVELOPMENT)..."
echo "   Project ID: $PROJECT_ID"
echo "   Scheduler Location: $SCHEDULER_LOCATION (Cloud Scheduler region)"
echo "   Backend Region: me-west1 (where your service runs)"
echo "   Service URL: $SERVICE_URL (DEV)"
echo "   Schedule: Daily at 2:00 AM (Jerusalem time)"
echo "   Scheduler Name: $SCHEDULER_NAME"

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

# Create or update the scheduler job
echo "📝 Creating Cloud Scheduler job..."

if gcloud scheduler jobs describe $SCHEDULER_NAME --location=$REGION --project=$PROJECT_ID &>/dev/null; then
    echo "⚠️  Job already exists. Updating..."
    gcloud scheduler jobs update http $SCHEDULER_NAME \
      --location=$REGION \
      --uri="$SERVICE_URL/api/v1/internal/campaign-sync/scheduled" \
      --http-method="POST" \
      --headers="Content-Type=application/json,X-Internal-Auth-Token=${INTERNAL_AUTH_TOKEN}" \
      --attempt-deadline="600s" \
      --description="Daily campaign KPI sync job (DEVELOPMENT) - triggers at 2 AM Jerusalem time"
else
    gcloud scheduler jobs create http $SCHEDULER_NAME \
      --project=$PROJECT_ID \
      --location=$REGION \
      --schedule="0 2 * * *" \
      --time-zone="Asia/Jerusalem" \
      --uri="$SERVICE_URL/api/v1/internal/campaign-sync/scheduled" \
      --http-method="POST" \
      --headers="Content-Type=application/json,X-Internal-Auth-Token=${INTERNAL_AUTH_TOKEN}" \
      --attempt-deadline="600s" \
      --description="Daily campaign KPI sync job (DEVELOPMENT) - triggers at 2 AM Jerusalem time"
fi

echo "✅ Cloud Scheduler job created successfully!"
echo ""
echo "To update the job later, run:"
echo "  gcloud scheduler jobs update http $SCHEDULER_NAME --location=$REGION"
echo ""
echo "To delete the job, run:"
echo "  gcloud scheduler jobs delete $SCHEDULER_NAME --location=$REGION"

