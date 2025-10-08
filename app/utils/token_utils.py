"""
Token utilities for OAuth token management and refresh operations
Centralizes all token-related operations following DRY principles
"""

import logging
from typing import Optional, Dict, Any
from app.services.google_analytics_service import GoogleAnalyticsService
from app.services.facebook_service import FacebookService

logger = logging.getLogger(__name__)


async def refresh_user_ga4_tokens(ga_service: GoogleAnalyticsService, user_id: int) -> None:
    """
    Automatically refresh expired GA4 tokens for a user before executing agents.
    
    Args:
        ga_service: GoogleAnalyticsService instance
        user_id: User ID to refresh tokens for
    """
    try:
        logger.info(f"🔄 Refreshing GA4 tokens for user {user_id}")
        
        # Get all GA4 connections for the user
        connections = await ga_service.get_user_ga_connections(user_id)
        
        if not connections:
            logger.warning(f"⚠️ No GA4 connections found for user {user_id}")
            return
        
        # Refresh tokens for each connection
        for connection in connections:
            try:
                connection_id = connection.get('connection_id')
                if connection_id:
                    await ga_service.refresh_ga_token(connection_id)
                    logger.info(f"✅ Refreshed GA4 token for connection {connection_id}")
                else:
                    logger.warning(f"⚠️ No connection_id found for GA4 connection: {connection}")
            except Exception as e:
                logger.error(f"❌ Failed to refresh GA4 token for connection {connection.get('connection_id')}: {e}")
                
    except Exception as e:
        logger.error(f"❌ Error refreshing GA4 tokens for user {user_id}: {e}")




async def refresh_user_google_ads_tokens(google_ads_service, user_id: int) -> None:
    """
    Automatically refresh expired Google Ads tokens for a user before executing agents.
    
    Args:
        google_ads_service: GoogleAdsService instance
        user_id: User ID to refresh tokens for
    """
    try:
        logger.info(f"🔄 Refreshing Google Ads tokens for user {user_id}")
        
        # Get all Google Ads connections for the user
        connections = await google_ads_service.get_user_google_ads_connections(user_id)
        
        if not connections:
            logger.warning(f"⚠️ No Google Ads connections found for user {user_id}")
            return
        
        # Refresh tokens for each connection
        for connection in connections:
            try:
                connection_id = connection.get('connection_id')
                if connection_id:
                    await google_ads_service.refresh_google_ads_token(connection_id)
                    logger.info(f"✅ Refreshed Google Ads token for connection {connection_id}")
                else:
                    logger.warning(f"⚠️ No connection_id found for Google Ads connection: {connection}")
            except Exception as e:
                logger.error(f"❌ Failed to refresh Google Ads token for connection {connection.get('connection_id')}: {e}")
                
    except Exception as e:
        logger.error(f"❌ Error refreshing Google Ads tokens for user {user_id}: {e}")



async def refresh_user_facebook_tokens(facebook_service: FacebookService, user_id: int) -> None:
    """
    Automatically refresh expired Facebook tokens for a user before executing agents.
    
    Args:
        facebook_service: FacebookService instance
        user_id: User ID to refresh tokens for
    """
    try:
        logger.info(f"🔄 Refreshing Facebook tokens for user {user_id}")
        
        # Get all Facebook connections for the user (both social media and advertising)
        social_connections = await facebook_service.get_facebook_connection_for_user(
            user_id=user_id,
            subclient_id=None,  # Get all subclients
            asset_type="SOCIAL_MEDIA"
        )
        
        ad_connections = await facebook_service.get_facebook_connection_for_user(
            user_id=user_id,
            subclient_id=None,  # Get all subclients
            asset_type="ADVERTISING"
        )
        
        all_connections = []
        if social_connections:
            all_connections.extend(social_connections)
        if ad_connections:
            all_connections.extend(ad_connections)
        
        if not all_connections:
            logger.warning(f"⚠️ No Facebook connections found for user {user_id}")
            return
        
        # Refresh tokens for each connection
        for connection in all_connections:
            try:
                connection_id = connection.get('connection_id')
                if connection_id:
                    await facebook_service.refresh_facebook_token(connection_id)
                    logger.info(f"✅ Refreshed Facebook token for connection {connection_id}")
                else:
                    logger.warning(f"⚠️ No connection_id found for Facebook connection: {connection}")
            except Exception as e:
                logger.error(f"❌ Failed to refresh Facebook token for connection {connection.get('connection_id')}: {e}")
                
    except Exception as e:
        logger.error(f"❌ Error refreshing Facebook tokens for user {user_id}: {e}")



async def refresh_all_user_tokens(user_id: int) -> Dict[str, bool]:
    """
    Refresh all OAuth tokens for a user (GA4, Facebook, Google Ads)
    
    Args:
        user_id: User ID to refresh tokens for
        
    Returns:
        Dictionary with refresh status for each service
    """
    results = {
        'ga4': False,
        'facebook': False,
        'google_ads': False
    }
    
    try:
        # Refresh GA4 tokens
        try:
            ga_service = GoogleAnalyticsService()
            await refresh_user_ga4_tokens(ga_service, user_id)
            results['ga4'] = True
        except Exception as e:
            logger.error(f"❌ Failed to refresh GA4 tokens: {e}")
        
        # Refresh Facebook tokens
        try:
            facebook_service = FacebookService()
            await refresh_user_facebook_tokens(facebook_service, user_id)
            results['facebook'] = True
        except Exception as e:
            logger.error(f"❌ Failed to refresh Facebook tokens: {e}")
        
        # Refresh Google Ads tokens
        try:
            from app.services.google_ads_service import GoogleAdsService
            google_ads_service = GoogleAdsService()
            await refresh_user_google_ads_tokens(google_ads_service, user_id)
            results['google_ads'] = True
        except Exception as e:
            logger.error(f"❌ Failed to refresh Google Ads tokens: {e}")
            
    except Exception as e:
        logger.error(f"❌ Error in refresh_all_user_tokens for user {user_id}: {e}")
    
    return results
