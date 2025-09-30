"""
FastAPI application factory for SatoApp
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime

from app.config import get_settings
from app.config.database import init_database
from app.config.logging import setup_logging, get_logger
from app.api import api_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.websocket import router as websocket_router
from app.core.security import verify_api_key

logger = get_logger("main")




@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    setup_logging()
    
    # VALIDATE CRITICAL ENVIRONMENT VARIABLES
    settings = get_settings()
    
    required_env_vars = {
        "GEMINI_API_KEY": settings.gemini_api_key,
        "DATABASE_URL": settings.database_url,
        "API_TOKEN": settings.api_token,
        "SECRET_KEY": settings.secret_key
    }
    
    missing_vars = [var for var, value in required_env_vars.items() if not value]
    if missing_vars:
        error_msg = f"❌ Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    logger.info("✅ All required environment variables are present")
    
    init_database()
    yield
    # Shutdown
    pass


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        description="Multi-agent AI system powered by CrewAI for SEO analysis and optimization",
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan
    )
    
    # Add CORS middleware (including WebSocket support)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://localhost:3000",  # HTTPS frontend
            "http://localhost:3000",   # HTTP frontend (fallback)
            "https://sato-frontend-397762748853.me-west1.run.app",  # Production frontend
            "https://localhost:8000",  # HTTPS backend (for testing)
            "http://localhost:8000",   # HTTP backend (for testing)
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health_router, tags=["health"])
    app.include_router(websocket_router, prefix="/api/v1", tags=["websocket"])
    app.include_router(api_router)
    
    # Add a simple test endpoint
    @app.get("/test-webhook")
    def test_webhook():
        """Simple test endpoint to verify deployment"""
        return {"message": "Webhook endpoint is working!", "timestamp": datetime.utcnow().isoformat()}
    
    return app


# Create application instance
app = create_app()
