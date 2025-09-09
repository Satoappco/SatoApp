#!/bin/bash

# Sato AI Crew Deployment Script
echo "🚀 Deploying Sato AI Crew to Google Cloud Run..."
echo "This deploys the integrated FastAPI + crewAI solution"

# Check if OpenAI API key is set
if grep -q "your_openai_api_key_here" .env; then
    echo "❌ Please update your .env file with your actual OpenAI API key first!"
    echo "Edit .env and replace 'your_openai_api_key_here' with your real API key"
    exit 1
fi

echo "📋 Deployment Configuration:"
echo "  - Service: sato-ai-crew"
echo "  - Region: us-central1"
echo "  - Memory: 2Gi (increased for AI processing)"
echo "  - CPU: 2 (increased for AI processing)"
echo "  - Timeout: 900s (15 minutes for long AI tasks)"
echo "  - Database: Private IP PostgreSQL"
echo ""

# Deploy to Google Cloud Run with optimized settings for AI workloads
gcloud run deploy sato-ai-crew \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --concurrency 10 \
  --max-instances 5 \
  --set-env-vars \
    DB_HOST=10.80.0.3,\
    DB_PORT=5432,\
    DB_NAME=sato,\
    DB_USER=postgres,\
    DB_PASSWORD=SatoDB_92vN!fG7kAq4hRzLwYx2!PmE,\
    GOOGLE_CLOUD_SQL=true,\
    DB_ECHO=false,\
    API_KEY=SatoLogos,\
    OPENAI_API_KEY=$(grep OPENAI_API_KEY .env | cut -d'=' -f2)

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Deployment completed successfully!"
    echo ""
    echo "🌐 Your Sato AI Crew API is now available:"
    echo "  - Health check: GET https://sato-ai-crew-[hash]-uc.a.run.app/"
    echo "  - Run crew: POST https://sato-ai-crew-[hash]-uc.a.run.app/crew"
    echo "  - Simple crew: POST https://sato-ai-crew-[hash]-uc.a.run.app/crew/simple"
    echo ""
    echo "🔗 Test with curl:"
    echo 'curl -X POST "https://your-url/crew" \'
    echo '  -H "Content-Type: application/json" \'
    echo '  -d '\''{"topic": "AI market trends"}'\'''
    echo ""
    echo "📚 See API_DOCUMENTATION.md for full usage guide"
else
    echo ""
    echo "❌ Deployment failed!"
    echo "Check the error messages above and try again."
    exit 1
fi
