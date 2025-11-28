"""
API version 1 router
"""

import os
from fastapi import APIRouter
from .routes import (
    agents,
    health,
    webhooks,
    # websocket,
    auth,
    google_analytics,
    google_analytics_oauth,
    google_ads,
    google_ads_oauth,
    facebook,
    facebook_oauth,
    facebook_page_oauth,
    facebook_marketing_oauth,
    admin,
    agencies,
    property_selections,
    digital_assets,
    campaigners,
    customers,
    # crewai,
    database_management,
    customer_data,
    countries_currencies,
    settings,
    oauth_state,
    campaign_sync,
    crew_sessions,
    logs,
    customer_assignments,
    traces,
    chat_feedback,
    metrics,
    tasks
)
from app.api.v1.routes.chat import router as chat_router

# Conditionally import debug routes ONLY in development
if os.getenv("ENVIRONMENT", "production") in ["development", "dev", "local"]:
    from .routes import debug_campaigners
    print("⚠️ DEBUG MODE: Debug campaigners endpoint enabled at /api/v1/debug/campaigners/{id}")

api_router = APIRouter(prefix="/api/v1")

# Include all route modules
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["authentication"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
# api_router.include_router(websocket.router, tags=["websocket"])
# api_router.include_router(crewai.router, tags=["crewai"])
api_router.include_router(google_analytics.router, tags=["google-analytics"])
api_router.include_router(google_analytics_oauth.router, tags=["google-analytics-oauth"])
api_router.include_router(google_ads.router, tags=["google-ads"])
api_router.include_router(google_ads_oauth.router, tags=["google-ads-oauth"])
api_router.include_router(facebook.router, tags=["facebook"])
api_router.include_router(facebook_oauth.router, tags=["facebook-oauth"])
api_router.include_router(facebook_page_oauth.router, tags=["facebook-page-oauth"])
api_router.include_router(facebook_marketing_oauth.router, tags=["facebook-marketing-oauth"])
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(agencies.router, tags=["agencies"])
api_router.include_router(property_selections.router, tags=["property-selections"])
api_router.include_router(digital_assets.router, tags=["digital-assets"])
api_router.include_router(campaigners.router, tags=["campaigners"])
api_router.include_router(customers.router, tags=["customers"])
api_router.include_router(database_management.router, tags=["database-management"])
api_router.include_router(customer_data.router, tags=["customer-data"])
api_router.include_router(chat_router, tags=["chat"])
api_router.include_router(countries_currencies.router, prefix="/constants", tags=["constants"])
api_router.include_router(settings.router, tags=["settings"])
api_router.include_router(oauth_state.router, tags=["oauth-state"])
api_router.include_router(campaign_sync.router, tags=["campaign-sync"])
api_router.include_router(crew_sessions.router, tags=["crew-sessions"])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"])
api_router.include_router(customer_assignments.router, prefix="/customers", tags=["customer-assignments"])
api_router.include_router(traces.router, tags=["traces"])
api_router.include_router(chat_feedback.router, prefix="/chat", tags=["chat-feedback"])
api_router.include_router(metrics.router, tags=["metrics"])
api_router.include_router(tasks.router, tags=["tasks"])

# Conditionally include debug routes ONLY in development
if os.getenv("ENVIRONMENT", "production") in ["development", "dev", "local"]:
    api_router.include_router(debug_campaigners.router, tags=["debug"])

__all__ = ["api_router"]
