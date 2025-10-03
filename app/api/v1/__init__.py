"""
API version 1 router
"""

from fastapi import APIRouter
from .routes import (
    agents, 
    health, 
    webhooks, 
    auth, 
    google_analytics, 
    google_analytics_oauth, 
    google_ads, 
    google_ads_oauth, 
    crewai_analysis, 
    facebook, 
    facebook_oauth, 
    facebook_page_oauth, 
    facebook_marketing_oauth, 
    admin, 
    customers, 
    property_selections, 
    users,
    crewai
)


api_router = APIRouter(prefix="/api/v1")

# Include all route modules
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["authentication"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(google_analytics.router, tags=["google-analytics"])
api_router.include_router(google_analytics_oauth.router, tags=["google-analytics-oauth"])
api_router.include_router(google_ads.router, tags=["google-ads"])
api_router.include_router(google_ads_oauth.router, tags=["google-ads-oauth"])
api_router.include_router(facebook.router, tags=["facebook"])
api_router.include_router(facebook_oauth.router, tags=["facebook-oauth"])
api_router.include_router(facebook_page_oauth.router, tags=["facebook-page-oauth"])
api_router.include_router(facebook_marketing_oauth.router, tags=["facebook-marketing-oauth"])
api_router.include_router(crewai_analysis.router, tags=["crewai"])
api_router.include_router(crewai.router, tags=["crewai"])
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(customers.router, tags=["customers"])
api_router.include_router(property_selections.router, tags=["property-selections"])
api_router.include_router(users.router, tags=["users"])

__all__ = ["api_router"]
