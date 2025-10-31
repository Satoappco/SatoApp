"""
Utilities for Sato AI Platform
Organized by functionality following best practices
"""

# Agent utilities
# from .agent_utils import get_tools_for_agent

# Token utilities
from .token_utils import (
    refresh_user_ga4_tokens,
    refresh_user_facebook_tokens,
    refresh_user_google_ads_tokens,
    refresh_all_user_tokens
)

# Data utilities
from .data_utils import (
    format_analytics_data,
    combine_multiple_data_sources
)

# Connection utilities
from .connection_utils import (
    get_facebook_connections,
    get_ga4_connections,
    get_google_ads_connections,
    get_connection_by_id,
    get_user_connections_summary,
    validate_connection_access
)

# Auth utilities
from .auth_utils import (
    build_token_data,
    compute_expires_at,
    create_token_pair,
    create_campaigner_response
)

# Existing utilities
from .async_utils import run_async_in_thread
from .date_utils import *

__all__ = [
    # Agent utilities
    "get_tools_for_agent",
    
    # Token utilities
    "refresh_user_ga4_tokens",
    "refresh_user_facebook_tokens", 
    "refresh_user_google_ads_tokens",
    "refresh_all_user_tokens",
    
    # Data utilities
    "format_analytics_data",
    "combine_multiple_data_sources",
    
    # Connection utilities
    "get_facebook_connections",
    "get_ga4_connections",
    "get_google_ads_connections",
    "get_connection_by_id",
    "get_user_connections_summary",
    "validate_connection_access",
    
    # Auth utilities
    "build_token_data",
    "compute_expires_at",
    "create_token_pair",
    "create_campaigner_response",
    
    # Existing utilities
    "run_async_in_thread",
]
