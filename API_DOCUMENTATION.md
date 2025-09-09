# Sato AI Crew API Documentation

## 🎯 **Problem Solved**

**Before**: crewAI only worked via CLI (`crewai run`) - couldn't run on Google Cloud Run
**After**: crewAI now accessible via HTTP API calls - perfect for cloud deployment!

## 🚀 **Available APIs**

### **1. FastAPI Server (`server.py`) - Port 8080**

#### **Health Check**
```http
GET /
```
**Response:**
```json
{
  "status": "ok",
  "service": "Sato AI Crew API", 
  "timestamp": "2025-01-03T10:30:00.000Z"
}
```

#### **Run Sato Crew (Full Response)**
```http
POST /crew
Content-Type: application/json

{
  "topic": "Marketing strategies for 2025",
  "current_year": "2025"
}
```
**Response:**
```json
{
  "result": "Detailed research and analysis report...",
  "topic": "Marketing strategies for 2025",
  "execution_time": 45.2,
  "timestamp": "2025-01-03T10:35:45.000Z"
}
```

#### **Run Sato Crew (Simple Response)**
```http
POST /crew/simple
Content-Type: application/json

{
  "topic": "AI trends"
}
```
**Response:**
```json
{
  "result": "AI research report content..."
}
```

### **2. Flask Webhook Server (`webhook_server.py`) - Port 8080**

#### **Standard Webhook (Data Logging)**
```http
POST /webhook
Authorization: Bearer SatoLogos
Content-Type: application/json

{
  "user_name": "John Doe",
  "user_choice": "Marketing Analysis",
  "topic": "Digital marketing trends"
}
```

#### **Webhook + Crew Trigger (NEW!)**
```http
POST /webhook/trigger-crew
Authorization: Bearer SatoLogos
Content-Type: application/json

{
  "user_name": "John Doe", 
  "user_choice": "Marketing Analysis",
  "topic": "Digital marketing trends"
}
```
**Response:**
```json
{
  "message": "Crew executed for user: John Doe",
  "entry_id": 123,
  "topic": "Digital marketing trends",
  "crew_result": "Detailed AI analysis...",
  "timestamp": "2025-01-03T10:30:00.000Z"
}
```

#### **Get Recent Entries**
```http
GET /webhook/recent?limit=10
Authorization: Bearer SatoLogos
```

#### **Health Check**
```http
GET /health
Authorization: Bearer SatoLogos
```

## 🔧 **Deployment Architecture**

### **Google Cloud Run Deployment**
```bash
# Deploy FastAPI server (main AI service)
gcloud run deploy sato-fastapi \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=your_key,DB_HOST=10.80.0.3,...

# Deploy Flask webhook (if needed separately)  
gcloud run deploy sato-webhook \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars API_KEY=SatoLogos,DB_HOST=10.80.0.3,...
```

### **Single Deployment (Recommended)**
Deploy just the FastAPI server - it includes all crewAI functionality!

## 📝 **Usage Examples**

### **Direct API Call**
```bash
curl -X POST "https://your-app-url/crew" \
  -H "Content-Type: application/json" \
  -d '{"topic": "AI market analysis"}'
```

### **From Dialogflow/Chatbot**
```bash
curl -X POST "https://your-app-url/webhook/trigger-crew" \
  -H "Authorization: Bearer SatoLogos" \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "Customer123",
    "topic": "Product recommendations"
  }'
```

### **From Frontend Application**
```javascript
const response = await fetch('https://your-app-url/crew', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    topic: 'Market research for startups',
    current_year: '2025'
  })
});

const result = await response.json();
console.log(result.result); // AI analysis
```

## 🎯 **Key Benefits**

✅ **Web-Accessible**: No more CLI dependency  
✅ **Cloud-Ready**: Perfect for Google Cloud Run  
✅ **Scalable**: Handle multiple concurrent requests  
✅ **Integrated**: Database logging + AI processing  
✅ **Flexible**: Multiple endpoints for different use cases  
✅ **Production-Ready**: Error handling, monitoring, health checks  

## 🔐 **Security**

- **FastAPI**: No authentication (can be added)
- **Webhook**: Bearer token authentication required
- **Database**: Private IP connection to PostgreSQL
- **Secrets**: Use Google Secret Manager for production

## 📊 **Monitoring**

- **Health checks** on both services
- **Execution time** tracking
- **Database connectivity** monitoring
- **Error logging** and reporting

Your crewAI is now fully web-enabled and ready for production deployment! 🎉
