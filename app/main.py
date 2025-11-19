"""
FastAPI application factory for SatoApp
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import time

# Load environment variables from .env file
load_dotenv()

from fastapi import HTTPException, Depends
from pydantic import BaseModel, ValidationError
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

    # Initialize file-based logging
    from app.core.file_logger import initialize_file_logging
    initialize_file_logging()
    logger.info("✅ File-based logging initialized")

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
    
    # Add request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        # Log incoming API requests and responses
        start_time = time.time()
        # Print directly to stdout for immediate visibility
        # print(f"🌐 REQUEST: {request.method} {request.url.path} Query: {dict(request.query_params)}")
        logger.debug(f"📥 {request.method} {request.url.path} - Query: {dict(request.query_params)} - Client: {request.client.host if request.client else 'unknown'}")
        response = await call_next(request)
        process_time = time.time() - start_time
        # print(f"🌐 RESPONSE: {request.method} {request.url.path} Status: {response.status_code} Time: {process_time:.3f}s")
        logger.debug(f"📤 {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s")
        return response

    # Add CORS middleware (including WebSocket support)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",    # HTTP frontend (local)
            "https://localhost:3000",   # HTTPS frontend (local)
            "http://localhost:8000",    # HTTP backend (for testing)
            "https://localhost:8000",   # HTTPS backend (for testing)
            "https://sato-frontend-397762748853.me-west1.run.app",  # Production frontend
            "https://sato-frontend-dev-397762748853.me-west1.run.app",  # Development frontend
            "https://sato-frontend-dor-397762748853.me-west1.run.app",  # Dor environment frontend
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Add custom exception handler for validation errors
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Custom handler for Pydantic validation errors"""
        logger.error(f"Validation error on {request.url}: {exc.errors()}")
        logger.error(f"Request body: {await request.body()}")
        
        # Convert errors to serializable format
        serializable_errors = []
        for error in exc.errors():
            serializable_error = {
                "loc": error.get("loc", []),
                "msg": str(error.get("msg", "")),
                "type": error.get("type", "")
            }
            serializable_errors.append(serializable_error)
        
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "message": "Request validation failed",
                    "errors": serializable_errors,
                    "body": str(exc.body) if exc.body else None
                }
            }
        )
    
    # Include routers
    app.include_router(health_router, tags=["health"])
    app.include_router(websocket_router, prefix="/api/v1", tags=["websocket"])
    app.include_router(api_router)
    
    # crewai router is now included in the normal api_router flow
    
    # Add a simple test endpoint
    @app.get("/test-webhook")
    def test_webhook():
        """Simple test endpoint to verify deployment"""
        return {"message": "Webhook endpoint is working!", "timestamp": datetime.utcnow().isoformat()}
    
    return app


# Create application instance
app = create_app()
