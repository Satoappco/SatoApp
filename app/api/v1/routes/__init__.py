"""
API route modules
"""

# Import modules individually to avoid circular imports
from . import agents
from . import health
from . import webhooks
from . import auth
from . import google_analytics
from . import google_analytics_oauth
from . import google_ads
from . import google_ads_oauth
from . import crewai_analysis
from . import facebook
from . import facebook_oauth
from . import facebook_page_oauth
from . import facebook_marketing_oauth
from . import admin
from . import customers
from . import property_selections
from . import digital_assets
from . import users

# NOTE: crewai_test is NOT imported here to avoid circular import in Python 3.11
# It's registered directly in main.py after all other modules are initialized

__all__ = [
    "agents", "health", "webhooks", "auth", "google_analytics", 
    "google_analytics_oauth", "google_ads", "google_ads_oauth", 
    "crewai_analysis", "facebook", "facebook_oauth", 
    "facebook_page_oauth", "facebook_marketing_oauth", "admin", 
    "customers", "property_selections", "digital_assets", "users"
]