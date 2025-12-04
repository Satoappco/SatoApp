"""
Health check routes
"""

from fastapi import APIRouter
from datetime import datetime
from app.config import get_settings

settings = get_settings()
router = APIRouter()


@router.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/")
def root():
    """Root endpoint"""
    return {
        "message": settings.app_name,
        "version": settings.app_version,
        "status": "active",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
