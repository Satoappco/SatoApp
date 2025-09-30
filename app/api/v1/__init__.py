"""
API version 1 router
"""

from fastapi import APIRouter
from .routes import agents, health, webhooks, auth, google_analytics, google_analytics_oauth, google_ads, crewai_analysis, crewai_test, facebook, facebook_oauth, admin, customers

api_router = APIRouter(prefix="/api/v1")

# Include all route modules
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["authentication"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(google_analytics.router, tags=["google-analytics"])
api_router.include_router(google_analytics_oauth.router, tags=["google-analytics-oauth"])
api_router.include_router(google_ads.router, tags=["google-ads"])
api_router.include_router(facebook.router, tags=["facebook"])
api_router.include_router(facebook_oauth.router, tags=["facebook-oauth"])
api_router.include_router(crewai_analysis.router, tags=["crewai"])
api_router.include_router(crewai_test.router, tags=["crewai-test"])
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(customers.router, tags=["customers"])

__all__ = ["api_router"]
