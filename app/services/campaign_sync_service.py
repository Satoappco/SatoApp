"""
Campaign KPI Sync Service
Fetches current campaign metrics and updates KPI Values
"""

import os
import re
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlmodel import select, and_, or_

from app.config.database import get_session
from app.models.analytics import KpiGoal, KpiValue, Connection, DigitalAsset, AssetType
from app.services.google_ads_service import GoogleAdsService
from app.services.facebook_service import FacebookService
from app.utils.connection_utils import get_google_ads_connections, get_facebook_connections


def get_google_client_id() -> str:
    """Get Google client ID from environment"""
    from dotenv import load_dotenv
    load_dotenv()
    return os.getenv("GOOGLE_CLIENT_ID", "")


def get_google_client_secret() -> str:
    """Get Google client secret from environment"""
    from dotenv import load_dotenv
    load_dotenv()
    return os.getenv("GOOGLE_CLIENT_SECRET", "")


class CampaignSyncService:
    """Service for syncing campaign metrics and updating KPI values"""
    
    def __init__(self):
        self.google_ads_service = GoogleAdsService()
        self.facebook_service = FacebookService()
    
    def parse_kpi_type(self, kpi_string: Optional[str]) -> Optional[str]:
        """
        Parse KPI type from string like "CPA <$15" or "CTR >5%"
        Returns the KPI type (CPA, CTR, CPC, Clicks, etc.)
        """
        if not kpi_string:
            return None
        
        # Remove direction and value, keep only KPI type
        # Examples: "CPA <$15" -> "CPA", "CTR >5%" -> "CTR"
        kpi_string = kpi_string.strip()
        
        # Extract first word/term (KPI type)
        parts = re.split(r'[<>=]', kpi_string)
        if parts:
            return parts[0].strip()
        
        return None
    
    def get_metrics_for_objective(self, objective: str, metrics: Dict[str, Any]) -> List[str]:
        """
        Get list of available KPI types based on campaign objective
        This determines which metrics are relevant for the goal
        """
        # Common metrics available for all objectives
        available_metrics = ['impressions', 'clicks', 'cost_micros', 'conversions', 'conversions_value', 'ctr', 'average_cpc']
        
        # Objective-specific additional metrics could be added here
        # For now, we use all available metrics
        return available_metrics
    
    def calculate_ad_score(self, metrics: Dict[str, Any], kpi_goal: KpiGoal) -> Optional[int]:
        """
        Calculate ad score (0-100) based on performance metrics
        Score based on: CTR (30%), Conversion Rate (40%), Cost Efficiency (30%)
        """
        try:
            clicks = metrics.get('clicks', 0)
            impressions = metrics.get('impressions', 0)
            conversions = metrics.get('conversions', 0)
            cost_micros = metrics.get('cost_micros', 0)
            conversions_value = metrics.get('conversions_value', 0)
            
            # If no data, return None (don't update score)
            if impressions == 0 or clicks == 0:
                return None
            
            # Calculate CTR (0-100)
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            # Score: 10 = perfect, 0 = very bad (penalty for < 1%)
            ctr_score = min(10, max(0, (ctr - 1) / 9 * 10)) if ctr >= 1 else max(0, ctr * 10)
            
            # Calculate Conversion Rate (0-100)
            conversion_rate = (conversions / clicks * 100) if clicks > 0 else 0
            # Score: 10 = 50%+, 0 = 0%
            conv_score = min(10, conversion_rate / 5) if conversion_rate > 0 else 0
            
            # Calculate Cost Efficiency (0-100)
            # ROAS = Revenue / Cost (higher is better)
            # Efficiency: 10 = ROAS > 4x, 0 = ROAS < 0.5x
            cost = cost_micros / 1_000_000 if cost_micros > 0 else 0
            roas = conversions_value / cost if cost > 0 else 0
            efficiency_score = min(10, max(0, (roas - 0.5) / 3.5 * 10)) if roas > 0 else 0
            
            # Weighted score: CTR 30% + Conv Rate 40% + Efficiency 30%
            weighted_score = (ctr_score * 0.3 + conv_score * 0.4 + efficiency_score * 0.3) * 10
            
            # Round to 0-100
            final_score = int(round(weighted_score))
            
            print(f"   📊 Ad Score Calculation:")
            print(f"      CTR: {ctr:.2f}% → {ctr_score:.1f}/10 (30% weight)")
            print(f"      Conv Rate: {conversion_rate:.2f}% → {conv_score:.1f}/10 (40% weight)")
            print(f"      ROAS: {roas:.2f}x → {efficiency_score:.1f}/10 (30% weight)")
            print(f"      Final Score: {final_score}/100")
            
            return final_score
            
        except Exception as e:
            print(f"❌ Error calculating ad score: {str(e)}")
            return None
    
    def calculate_kpi_value(self, kpi_type: Optional[str], metrics: Dict[str, Any]) -> str:
        """
        Calculate KPI value from raw metrics
        Returns formatted string like "CPA $12.50" or "CTR 7.2%"
        """
        if not kpi_type or not metrics:
            return ""
        
        try:
            if kpi_type == "CPA":  # Cost Per Acquisition
                cost_micros = metrics.get('cost_micros', 0)
                cost = cost_micros / 1_000_000
                conversions = metrics.get('conversions', 0)
                value = cost / conversions if conversions > 0 else 0
                return f"CPA ${value:.2f}"
            
            elif kpi_type == "CTR":  # Click-Through Rate
                clicks = metrics.get('clicks', 0)
                impressions = metrics.get('impressions', 0)
                value = (clicks / impressions * 100) if impressions > 0 else 0
                return f"CTR {value:.2f}%"
            
            elif kpi_type == "CPC":  # Cost Per Click
                cost_micros = metrics.get('cost_micros', 0)
                cost = cost_micros / 1_000_000
                clicks = metrics.get('clicks', 0)
                value = cost / clicks if clicks > 0 else 0
                return f"CPC ${value:.2f}"
            
            elif kpi_type == "Clicks":
                return f"Clicks {metrics.get('clicks', 0)}"
            
            elif kpi_type == "Impressions":
                return f"Impressions {metrics.get('impressions', 0)}"
            
            elif kpi_type == "Conversions":
                return f"Conversions {metrics.get('conversions', 0)}"
            
            elif kpi_type == "Cost" or kpi_type == "Spend":
                cost_micros = metrics.get('cost_micros', 0)
                cost = cost_micros / 1_000_000
                return f"${cost:.2f}"
            
            elif kpi_type == "ROAS":  # Return on Ad Spend
                cost_micros = metrics.get('cost_micros', 0)
                cost = cost_micros / 1_000_000
                conversion_value = metrics.get('conversions_value', 0)
                value = conversion_value / cost if cost > 0 else 0
                return f"ROAS {value:.2f}x"
            
            elif kpi_type == "Revenue" or kpi_type == "Rev.":
                conversion_value = metrics.get('conversions_value', 0)
                return f"Revenue ${conversion_value:.2f}"
            
            elif kpi_type == "CVR" or kpi_type == "CvR":  # Conversion Rate
                conversions = metrics.get('conversions', 0)
                clicks = metrics.get('clicks', 0)
                value = (conversions / clicks * 100) if clicks > 0 else 0
                return f"CVR {value:.2f}%"
            
            elif kpi_type == "Conv.va" or kpi_type == "Conversions Value":
                conversion_value = metrics.get('conversions_value', 0)
                return f"Conv.va ${conversion_value:.2f}"
            
            # Facebook-specific metrics
            elif kpi_type == "CPM":  # Cost Per Mille
                spend = metrics.get('spend', 0)
                impressions = metrics.get('impressions', 0)
                value = (spend / impressions * 1000) if impressions > 0 else 0
                return f"CPM ${value:.2f}"
            
            return f"{kpi_type} {metrics.get('value', 'N/A')}"
        
        except Exception as e:
            return f"Error: {str(e)}"
    
    def fetch_google_ads_campaign_metrics(self, campaign_id: str, ad_group_id: Optional[str], ad_id: Optional[str], connection: Connection, digital_asset: DigitalAsset) -> Optional[Dict[str, Any]]:
        """Fetch campaign metrics from Google Ads API"""
        try:
            # Calculate yesterday's date for data fetching
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Note: Token refresh is handled automatically by GoogleAdsClient
            # when we pass the refresh_token in load_from_dict()
            
            # Decrypt refresh token
            refresh_token = self.google_ads_service._decrypt_token(connection.refresh_token_enc)
            
            # Get developer token
            developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
            if not developer_token:
                print("❌ Google Ads developer token not configured")
                return None
            
            # Create Google Ads client
            from google.ads.googleads.client import GoogleAdsClient
            
            client = GoogleAdsClient.load_from_dict({
                "developer_token": developer_token,
                "client_id": get_google_client_id(),
                "client_secret": get_google_client_secret(),
                "refresh_token": refresh_token,
                "use_proto_plus": True
            })
            
            # Get service
            ga_service = client.get_service("GoogleAdsService")
            
            # Get customer ID from digital asset
            customer_id = digital_asset.external_id
            
            # Build query based on granularity
            if ad_id:
                # Query specific ad metrics
                # Note: campaign_id may contain underscores, so we need to handle it carefully
                campaign_id_str = str(campaign_id).replace("'", "''")  # Escape quotes
                query = f"""
                    SELECT 
                        campaign.id,
                        campaign.name,
                        campaign.status,
                        ad_group.id,
                        ad_group.name,
                        ad_group_ad.ad.id,
                        ad_group_ad.status,
                        metrics.impressions,
                        metrics.clicks,
                        metrics.cost_micros,
                        metrics.conversions,
                        metrics.conversions_value,
                        metrics.ctr,
                        metrics.average_cpc
                    FROM ad_group_ad
                    WHERE campaign.id = '{campaign_id_str}'
                    AND ad_group.id = {ad_group_id}
                    AND ad_group_ad.ad.id = {ad_id}
                    AND segments.date = '{yesterday}'
                """
            elif ad_group_id:
                # Query ad group level metrics
                campaign_id_str = str(campaign_id).replace("'", "''")  # Escape quotes
                query = f"""
                    SELECT 
                        campaign.id,
                        campaign.name,
                        campaign.status,
                        ad_group.id,
                        ad_group.name,
                        metrics.impressions,
                        metrics.clicks,
                        metrics.cost_micros,
                        metrics.conversions,
                        metrics.conversions_value,
                        metrics.ctr,
                        metrics.average_cpc
                    FROM ad_group
                    WHERE campaign.id = '{campaign_id_str}'
                    AND ad_group.id = {ad_group_id}
                    AND segments.date = '{yesterday}'
                """
            else:
                # Query campaign level metrics (fallback)
                campaign_id_str = str(campaign_id).replace("'", "''")  # Escape quotes
                query = f"""
                    SELECT 
                        campaign.id,
                        campaign.name,
                        campaign.status,
                        metrics.impressions,
                        metrics.clicks,
                        metrics.cost_micros,
                        metrics.conversions,
                        metrics.conversions_value,
                        metrics.ctr,
                        metrics.average_cpc
                    FROM campaign
                    WHERE campaign.id = '{campaign_id_str}'
                    AND segments.date = '{yesterday}'
                """
            
            # Execute query
            print(f"   🔍 Executing query for Google Ads Customer ID: {customer_id}")
            print(f"   📝 Query:\n{query}")
            try:
                response = ga_service.search(customer_id=customer_id, query=query)
            except Exception as query_error:
                print(f"   ❌ Query execution error: {query_error}")
                raise
            
            metrics = {}
            row_count = 0
            for row in response:
                row_count += 1
                # Safely extract all fields
                metrics = {
                    "campaign_id": getattr(row.campaign, 'id', campaign_id) if hasattr(row, 'campaign') else campaign_id,
                    "campaign_name": getattr(row.campaign, 'name', '') if hasattr(row, 'campaign') else '',
                    "campaign_status": getattr(row.campaign.status, 'name', 'ENABLED') if hasattr(row, 'campaign') and hasattr(row.campaign, 'status') else 'ENABLED',
                }
                
                # Add ad_group fields if available
                if hasattr(row, 'ad_group'):
                    if hasattr(row.ad_group, 'id'):
                        metrics["ad_group_id"] = row.ad_group.id
                    if hasattr(row.ad_group, 'name'):
                        metrics["ad_group_name"] = row.ad_group.name
                
                # Add ad fields if available - when querying FROM ad_group_ad, ad fields are nested
                if hasattr(row, 'ad_group_ad'):
                    if hasattr(row.ad_group_ad, 'ad') and hasattr(row.ad_group_ad.ad, 'id'):
                        try:
                            metrics["ad_id"] = row.ad_group_ad.ad.id
                        except AttributeError:
                            pass
                    if hasattr(row.ad_group_ad, 'status'):
                        try:
                            metrics["ad_status"] = row.ad_group_ad.status.name if hasattr(row.ad_group_ad.status, 'name') else 'UNKNOWN'
                        except AttributeError:
                            pass
                
                # Also check if ad fields are directly accessible (some query structures)
                if hasattr(row, 'ad') and hasattr(row.ad, 'id'):
                    try:
                        metrics["ad_id"] = row.ad.id
                    except AttributeError:
                        pass
                
                # Extract metrics
                if hasattr(row, 'metrics'):
                    metrics["impressions"] = getattr(row.metrics, 'impressions', 0)
                    metrics["clicks"] = getattr(row.metrics, 'clicks', 0)
                    metrics["cost_micros"] = getattr(row.metrics, 'cost_micros', 0)
                    metrics["conversions"] = getattr(row.metrics, 'conversions', 0)
                    metrics["conversions_value"] = getattr(row.metrics, 'conversions_value', 0)
                    metrics["ctr"] = getattr(row.metrics, 'ctr', 0) * 100 if hasattr(row.metrics, 'ctr') else 0  # Convert to percentage
                    metrics["average_cpc"] = getattr(row.metrics, 'average_cpc', 0)
                
                break  # Should only return one row
            
            if row_count == 0:
                print(f"   ⚠️ No data found for campaign {campaign_id}")
                return None
            
            print(f"   ✅ Found metrics: {list(metrics.keys())}")
            return metrics if metrics else None
        
        except Exception as e:
            print(f"❌ Error fetching Google Ads metrics: {str(e)}")
            return None
    
    def fetch_facebook_campaign_metrics(self, campaign_id: str, ad_set_id: Optional[str], ad_id: Optional[str], connection: Connection, digital_asset: DigitalAsset) -> Optional[Dict[str, Any]]:
        """Fetch campaign metrics from Facebook Marketing API"""
        try:
            # Calculate yesterday's date for data fetching
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Decrypt access token
            if isinstance(connection.access_token_enc, str):
                access_token = self.facebook_service._decrypt_token(connection.access_token_enc.encode('utf-8'))
            else:
                access_token = self.facebook_service._decrypt_token(connection.access_token_enc)
            
            # Get ad account ID from digital asset external_id (format: "act_1428787248149391")
            # Or fall back to meta if stored there
            ad_account_id = digital_asset.external_id
            if not ad_account_id or not ad_account_id.startswith('act_'):
                # Try to get from meta as fallback
                if isinstance(digital_asset.meta, dict):
                    ad_account_id = digital_asset.meta.get('ad_account_id')
            
            if not ad_account_id or not ad_account_id.startswith('act_'):
                print(f"❌ No valid ad account ID found in digital asset {digital_asset.id}")
                print(f"   external_id: {digital_asset.external_id}")
                print(f"   meta: {digital_asset.meta}")
                return None
            
            # Note: We skip token refresh here since this is a sync method (not async)
            # Token refresh is handled by the FacebookService when needed
            # If token is expired, the API call will fail and user will need to re-authenticate
            if connection.expires_at and connection.expires_at <= datetime.utcnow() + timedelta(minutes=5):
                print(f"⚠️ Token expiring soon for connection {connection.id} - attempting with current token")
            
            # Build URL based on granularity - Facebook uses ad_set (adgroup) and ad levels
            if ad_id:
                # Query specific ad metrics
                url = f"https://graph.facebook.com/{self.facebook_service.api_version}/{ad_id}/insights"
            elif ad_set_id:
                # Query ad set (ad group) metrics  
                url = f"https://graph.facebook.com/{self.facebook_service.api_version}/{ad_set_id}/insights"
            else:
                # Query campaign level metrics
                url = f"https://graph.facebook.com/{self.facebook_service.api_version}/{campaign_id}/insights"
            
            params = {
                'access_token': access_token,
                'fields': 'impressions,clicks,spend,conversions,ctr,cpm,cpc,reach,action_values',
                'time_range': json.dumps({
                    'since': yesterday,
                    'until': yesterday
                })
            }
            
            # Make API request
            response = requests.get(url, params=params)
            
            if response.status_code != 200:
                print(f"❌ Facebook API error: {response.status_code} - {response.text}")
                return None
            
            response_data = response.json()
            data = response_data.get('data', [])
            if not data:
                print(f"   ⚠️ No data for ad {ad_id or ad_set_id or campaign_id} on {yesterday}")
                return None
            
            # Parse Facebook metrics
            metrics_data = data[0]
            print(f"   ✅ Found Facebook metrics: {len(metrics_data)} fields")
            
            # Parse action_values to get conversion value
            action_values = metrics_data.get('action_values', [])
            conversions_value = 0
            if action_values:
                # Sum up all conversion values
                for action in action_values:
                    # Check for purchase/omni conversion actions
                    if action.get('action_type') in ['offsite_conversion.fb_pixel_purchase', 'omni_purchase', 'purchase']:
                        conversions_value += float(action.get('value', 0))
            
            metrics = {
                "campaign_id": campaign_id,
                "campaign_name": metrics_data.get('campaign_name', ''),
                "campaign_status": "ACTIVE",  # Facebook doesn't return status in insights
                "impressions": int(metrics_data.get('impressions', 0)),
                "clicks": int(metrics_data.get('clicks', 0)),
                "cost_micros": int(float(metrics_data.get('spend', 0)) * 1_000_000),  # Convert to micros
                "conversions": int(metrics_data.get('conversions', 0)),
                "conversions_value": conversions_value,  # Parse from action_values
                "ctr": float(metrics_data.get('ctr', 0)),
                "cpm": float(metrics_data.get('cpm', 0)),
                "cpc": float(metrics_data.get('cpc', 0)),
                "reach": int(metrics_data.get('reach', 0))
            }
            
            return metrics
        
        except Exception as e:
            print(f"❌ Error fetching Facebook metrics: {str(e)}")
            return None
    
    def update_kpi_value(self, kpi_goal: KpiGoal, metrics: Dict[str, Any]) -> bool:
        """
        Update KpiValue record with calculated KPIs from metrics
        Returns True if updated successfully
        """
        try:
            with get_session() as session:
                # Find existing KpiValue
                kpi_value = session.exec(
                    select(KpiValue).where(KpiValue.kpi_goal_id == kpi_goal.id)
                ).first()
                
                if not kpi_value:
                    print(f"⚠️ No KpiValue found for KpiGoal {kpi_goal.id} - creating one")
                    # Create a new KpiValue if it doesn't exist
                    kpi_value = KpiValue(
                        customer_id=kpi_goal.customer_id,
                        kpi_goal_id=kpi_goal.id,
                        campaign_id=kpi_goal.campaign_id,
                        campaign_name=kpi_goal.campaign_name,
                        campaign_status=kpi_goal.campaign_status,
                        ad_group_id=kpi_goal.ad_group_id,
                        ad_group_name=kpi_goal.ad_group_name,
                        ad_group_status=kpi_goal.ad_group_status,
                        ad_id=kpi_goal.ad_id,
                        ad_name=kpi_goal.ad_name,
                        ad_name_headline=kpi_goal.ad_name_headline,
                        ad_status=kpi_goal.ad_status,
                        ad_score=kpi_goal.ad_score,
                        advertising_channel=kpi_goal.advertising_channel,
                        campaign_objective=kpi_goal.campaign_objective,
                        daily_budget=kpi_goal.daily_budget,
                        spent=kpi_goal.spent,
                        target_audience=kpi_goal.target_audience,
                        landing_page=kpi_goal.landing_page,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    session.add(kpi_value)
                    session.flush()
                    print(f"✅ Created new KpiValue {kpi_value.id} for KpiGoal {kpi_goal.id}")
                
                # Parse and calculate KPIs
                primary_kpi_type = self.parse_kpi_type(kpi_goal.primary_kpi_1)
                secondary_kpi_1_type = self.parse_kpi_type(kpi_goal.secondary_kpi_1)
                secondary_kpi_2_type = self.parse_kpi_type(kpi_goal.secondary_kpi_2)
                secondary_kpi_3_type = self.parse_kpi_type(kpi_goal.secondary_kpi_3)
                
                # Calculate values
                if primary_kpi_type:
                    kpi_value.primary_kpi_1 = self.calculate_kpi_value(primary_kpi_type, metrics)
                
                if secondary_kpi_1_type:
                    kpi_value.secondary_kpi_1 = self.calculate_kpi_value(secondary_kpi_1_type, metrics)
                
                if secondary_kpi_2_type:
                    kpi_value.secondary_kpi_2 = self.calculate_kpi_value(secondary_kpi_2_type, metrics)
                
                if secondary_kpi_3_type:
                    kpi_value.secondary_kpi_3 = self.calculate_kpi_value(secondary_kpi_3_type, metrics)
                
                # Update spent and status
                if 'cost_micros' in metrics:
                    kpi_value.spent = metrics['cost_micros'] / 1_000_000
                
                if 'campaign_status' in metrics:
                    kpi_value.campaign_status = metrics['campaign_status']
                
                # Calculate and update ad_score based on performance
                ad_score = self.calculate_ad_score(metrics, kpi_goal)
                if ad_score is not None:
                    kpi_value.ad_score = ad_score
                
                # Update timestamp
                kpi_value.updated_at = datetime.utcnow()
                
                session.commit()
                return True
        
        except Exception as e:
            print(f"❌ Error updating KpiValue: {str(e)}")
            return False
    
    def sync_all_kpi_goals(self, customer_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Sync all KPI goals (or specific customer's goals)
        Returns summary with counts and errors
        """
        start_time = datetime.utcnow()
        kpi_goals_processed = 0
        kpi_values_updated = 0
        errors = []
        
        try:
            with get_session() as session:
                # Query KpiGoals
                query = select(KpiGoal)
                if customer_id:
                    query = query.where(KpiGoal.customer_id == customer_id)
                
                kpi_goals = session.exec(query).all()
                kpi_goals_processed = len(kpi_goals)
                
                print(f"📊 Found {kpi_goals_processed} KpiGoals to sync")
                if kpi_goals_processed == 0:
                    print(f"   ⚠️  No KpiGoals found for customer_id={customer_id}")
                    return {
                        "success": True,
                        "kpi_goals_processed": 0,
                        "kpi_values_updated": 0,
                        "errors_count": 0,
                        "error_details": [],
                        "duration_seconds": 0
                    }
                
                # Group by customer and channel
                by_customer_channel = {}
                for goal in kpi_goals:
                    key = (goal.customer_id, goal.advertising_channel)
                    if key not in by_customer_channel:
                        by_customer_channel[key] = []
                    by_customer_channel[key].append(goal)
                
                # Process each group
                for (customer_id, advertising_channel), goals in by_customer_channel.items():
                    print(f"🔄 Processing {len(goals)} goals for customer {customer_id}, channel: {advertising_channel}")
                    
                    # Get connections for this customer/channel
                    # Debug: log what channel we're looking for
                    print(f"   Looking for connections for channel: '{advertising_channel}'")
                    
                    if "Google Ads" in advertising_channel or "Google" in advertising_channel or "Search Ads" in advertising_channel:
                        connections = session.exec(
                            select(Connection, DigitalAsset).join(
                                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
                            ).where(
                                and_(
                                    Connection.customer_id == customer_id,
                                    or_(
                                        DigitalAsset.provider == "Google Ads",
                                        DigitalAsset.provider == "Google"
                                    ),
                                    or_(
                                        DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                                        DigitalAsset.asset_type == AssetType.GOOGLE_ADS_CAPS,
                                        DigitalAsset.asset_type == AssetType.ADVERTISING
                                    ),
                                    Connection.revoked == False
                                )
                            )
                        ).all()
                        
                        print(f"   Found {len(connections)} Google Ads connections")
                        if len(connections) == 0:
                            # Debug: Check all connections for this customer
                            all_connections = session.exec(
                                select(Connection, DigitalAsset).join(
                                    DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
                                ).where(
                                    Connection.customer_id == customer_id
                                )
                            ).all()
                            print(f"   DEBUG: Customer {customer_id} has {len(all_connections)} total connections:")
                            for c, a in all_connections:
                                print(f"      - {a.provider} / {a.asset_type} / revoked={c.revoked}")
                        for connection, digital_asset in connections:
                            for goal in goals:
                                print(f"   Fetching metrics for campaign {goal.campaign_id}, ad_group {goal.ad_group_id}, ad {goal.ad_id}")
                                try:
                                    metrics = self.fetch_google_ads_campaign_metrics(
                                        goal.campaign_id, 
                                        str(goal.ad_group_id) if goal.ad_group_id else None,
                                        str(goal.ad_id) if goal.ad_id else None,
                                        connection, 
                                        digital_asset
                                    )
                                    if metrics:
                                        print(f"   Updating KpiValue for KpiGoal {goal.id}")
                                        if self.update_kpi_value(goal, metrics):
                                            kpi_values_updated += 1
                                            print(f"   ✅ Updated KpiValue for KpiGoal {goal.id}")
                                        else:
                                            print(f"   ❌ Failed to update KpiValue for KpiGoal {goal.id}")
                                    else:
                                        errors.append(f"Campaign {goal.campaign_id} not found or no metrics")
                                except Exception as e:
                                    errors.append(f"Error syncing campaign {goal.campaign_id}: {str(e)}")
                    
                    elif "Facebook" in advertising_channel or "facebook" in advertising_channel.lower():
                        connections = session.exec(
                            select(Connection, DigitalAsset).join(
                                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
                            ).where(
                                and_(
                                    Connection.customer_id == customer_id,
                                    DigitalAsset.provider == "Facebook",
                                    or_(
                                        DigitalAsset.asset_type == AssetType.FACEBOOK_ADS,
                                        DigitalAsset.asset_type == AssetType.FACEBOOK_ADS_CAPS,
                                        DigitalAsset.asset_type == AssetType.ADVERTISING
                                    ),
                                    Connection.revoked == False
                                )
                            )
                        ).all()
                        
                        print(f"   Found {len(connections)} Facebook connections")
                        if len(connections) == 0:
                            # Debug: Check all connections for this customer
                            all_connections = session.exec(
                                select(Connection, DigitalAsset).join(
                                    DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
                                ).where(
                                    Connection.customer_id == customer_id
                                )
                            ).all()
                            print(f"   DEBUG: Customer {customer_id} has {len(all_connections)} total connections:")
                            for c, a in all_connections:
                                print(f"      - {a.provider} / {a.asset_type} / revoked={c.revoked}")
                        for connection, digital_asset in connections:
                            for goal in goals:
                                print(f"   Fetching metrics for campaign {goal.campaign_id}, ad_set {goal.ad_group_id}, ad {goal.ad_id}")
                                try:
                                    metrics = self.fetch_facebook_campaign_metrics(
                                        goal.campaign_id,
                                        str(goal.ad_group_id) if goal.ad_group_id else None,  # Facebook calls ad_group "ad_set"
                                        str(goal.ad_id) if goal.ad_id else None,
                                        connection,
                                        digital_asset
                                    )
                                    if metrics:
                                        print(f"   Updating KpiValue for KpiGoal {goal.id}")
                                        if self.update_kpi_value(goal, metrics):
                                            kpi_values_updated += 1
                                            print(f"   ✅ Updated KpiValue for KpiGoal {goal.id}")
                                        else:
                                            print(f"   ❌ Failed to update KpiValue for KpiGoal {goal.id}")
                                    else:
                                        errors.append(f"Campaign {goal.campaign_id} not found or no metrics")
                                except Exception as e:
                                    errors.append(f"Error syncing campaign {goal.campaign_id}: {str(e)}")
                    
                    else:
                        # Unknown advertising channel
                        print(f"   ⚠️ Unknown advertising channel: '{advertising_channel}' - skipping {len(goals)} goals")
                        errors.extend([f"Unknown advertising channel: {advertising_channel}"] * len(goals))
        
        except Exception as e:
            errors.append(f"Fatal error in sync: {str(e)}")
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            "success": True,
            "kpi_goals_processed": kpi_goals_processed,
            "kpi_values_updated": kpi_values_updated,
            "errors_count": len(errors),
            "error_details": errors[:10],  # Limit to first 10 errors
            "duration_seconds": round(duration, 2)
        }

