#!/bin/bash
# Usage: ./scripts/local_docker_build_and_deploy.sh SERVICE_NAME REGION PROJECT_ID REPO_NAME IMAGE_TAG YAML_FILE
SERVICE_NAME=${1:-sato-backend-dev}
REGION=${2:-me-west1}
PROJECT_ID=${3:-"superb-dream-470215-i7"}  # Your actual project ID
REPO_NAME=${4:-sato-repo}
IMAGE_TAG=${5:-latest}
YAML_FILE=${6:-env.cloudrun.yaml}
SCRIPT_DIR=$(dirname "$0")

# Step 0: Convert .env to YAML format for Cloud Run
$SCRIPT_DIR/convert_env_to_yaml.sh ${YAML_FILE}
if [ $? -ne 0 ]; then
    echo "❌ ERROR: Failed to convert .env to YAML format!"
    exit 1
fi


# Step 1: Build the Docker image locally
docker build -t $SERVICE_NAME:$IMAGE_TAG .

# Step 2: Tag the image for Artifact Registry
IMAGE_URI=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$SERVICE_NAME:$IMAGE_TAG
docker tag $SERVICE_NAME:$IMAGE_TAG $IMAGE_URI

# Step 3: Authenticate Docker to Artifact Registry
gcloud auth configure-docker $REGION-docker.pkg.dev

# Step 4: Push the image to Artifact Registry
docker push $IMAGE_URI

# # Step 5: Deploy to Cloud Run (pre-built image, no Cloud Build)
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_URI \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 3000 \
  --memory 2Gi \
  --cpu 2 \
  --max-instances 5 \
  --concurrency 10 \
  --execution-environment gen2 \
  --cpu-boost \
  --min-instances 1 \
  --timeout 300 \
  --env-vars-file "$YAML_FILE" 
  # --no-source


echo "✅ Deployment completed successfully!"