"""
API route modules
"""

# Import modules individually to avoid circular imports
from . import agents
from . import health
from . import webhooks
from . import websocket
from . import auth
from . import google_analytics
from . import google_analytics_oauth
from . import google_ads
from . import google_ads_oauth
from . import facebook
from . import facebook_oauth
from . import facebook_page_oauth
from . import facebook_marketing_oauth
from . import admin
from . import agencies
from . import property_selections
from . import digital_assets
from . import campaigners
from . import customers
from . import crewai
from . import database_management
from . import customer_data
from . import countries_currencies
from . import oauth_state
from . import campaign_sync
from . import logs
from . import customer_assignments
from . import metrics

__all__ = [
    "agents", "health", "webhooks", "websocket", "auth", "google_analytics",
    "google_analytics_oauth", "google_ads", "google_ads_oauth",
    "facebook", "facebook_oauth",
    "facebook_page_oauth", "facebook_marketing_oauth", "admin",
    "agencies", "property_selections", "digital_assets", "campaigners",
    "customers", "crewai", "database_management", "customer_data",
    "countries_currencies", "oauth_state", "campaign_sync", "logs",
    "customer_assignments", "metrics"
]