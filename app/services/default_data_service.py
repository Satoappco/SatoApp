"""
Default Data Service

This service creates default data for new users/agencies to provide
a working system from the start.
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlmodel import Session, select, and_
from app.config.database import get_session
from app.models.analytics import KpiGoal, KpiValue, KpiCatalog, KpiSettings, DefaultKpiSettings
from app.models.customer_data import RTMTable, QuestionsTable
from app.models.agents import AgentConfig
from app.models.users import Agency, Customer
import json
import logging

logger = logging.getLogger(__name__)


class DefaultDataService:
    """Service for creating default data for new users/agencies"""
    
    def __init__(self):
        self.default_questions = [
            "מה הביצועים של הקמפיין האחרון?",
            "איך נראית התנועה לאתר השבוע?",
            "מה ה-ROI של הקמפיינים שלנו?",
            "איזה קמפיין הכי מוצלח?",
            "איך נראית התנועה מהרשתות החברתיות?",
            "מה ה-CPA הממוצע שלנו?",
            "איך נראית ההמרה מהמובייל?",
            "מה ה-CTR של הקמפיינים שלנו?",
            "איך נראית התנועה האורגנית?",
            "מה ה-ROAS של הקמפיינים שלנו?"
        ]
    
    def create_default_data_for_agency(self, agency_id: int) -> Dict[str, Any]:
        """Create default data for a new agency"""
        try:
            with get_session() as session:
                # Create default KPI catalog entries (global, not agency-specific)
                self._create_default_kpi_catalog(session)
                
                # Create default agent configurations (global, not agency-specific)
                self._create_default_agent_configs(session)
                
                session.commit()
                
                logger.info(f"✅ Created default data for agency {agency_id}")
                return {"success": True, "message": "Default data created successfully"}
                
        except Exception as e:
            logger.error(f"❌ Failed to create default data for agency {agency_id}: {str(e)}")
            raise e
    
    def create_default_data_for_customer(self, customer_id: int, agency_id: int, campaigner_id: int) -> Dict[str, Any]:
        """Create default data for a new customer"""
        try:
            with get_session() as session:
                # Create default KPI settings from defaults
                self._create_default_kpi_settings(session, customer_id, agency_id, campaigner_id)
                
                # Create default questions (uses composite_id)
                self._create_default_questions(session, customer_id, agency_id, campaigner_id)
                
                # Create default RTM links (uses composite_id)
                self._create_default_rtm_links(session, customer_id, agency_id, campaigner_id)
                
                # Note: Digital assets and connections are created by users when they connect their accounts
                # No default data needed for these tables
                
                session.commit()
                
                logger.info(f"✅ Created default data for customer {customer_id}")
                return {"success": True, "message": "Default customer data created successfully"}
                
        except Exception as e:
            logger.error(f"❌ Failed to create default data for customer {customer_id}: {str(e)}")
            raise e
    
    def _create_default_kpi_catalog(self, session: Session):
        """Create default KPI catalog entries"""
        default_catalog_entries = [
            {
                "subtype": "ecommerce",
                "primary_metric": "Revenue",
                "primary_submetrics": '["Transactions","Avg. Order Value"]',
                "secondary_metric": "Conversion Rate",
                "secondary_submetrics": '["Sessions","Users"]',
                "lite_primary_metric": "Users",
                "lite_primary_submetrics": '["New Users","Sessions"]',
                "lite_secondary_metric": "Engagement",
                "lite_secondary_submetrics": '["Engaged Sessions","Avg. Engagement Time"]'
            },
            {
                "subtype": "leadgen",
                "primary_metric": "Leads Generated",
                "primary_submetrics": '["Conversion Rate","Conversions"]',
                "secondary_metric": "Traffic Volume",
                "secondary_submetrics": '["Users","Sessions"]',
                "lite_primary_metric": "Sessions",
                "lite_primary_submetrics": '["Users","New Users"]',
                "lite_secondary_metric": "Engagement",
                "lite_secondary_submetrics": '["Engaged Sessions","Event Count"]'
            },
            {
                "subtype": "content_blog",
                "primary_metric": "Engagement",
                "primary_submetrics": '["Avg. Engagement Time","Page Views"]',
                "secondary_metric": "Audience Growth",
                "secondary_submetrics": '["New Users","Returning Users"]',
                "lite_primary_metric": "Engagement",
                "lite_primary_submetrics": '["Avg. Engagement Time","Page Views"]',
                "lite_secondary_metric": "Audience Growth",
                "lite_secondary_submetrics": '["Users","Returning Users"]'
            }
        ]
        
        for entry in default_catalog_entries:
            # Check if entry already exists
            existing = session.exec(
                select(KpiCatalog).where(KpiCatalog.subtype == entry["subtype"])
            ).first()
            
            if not existing:
                catalog_entry = KpiCatalog(**entry)
                session.add(catalog_entry)
                logger.info(f"Created KPI catalog entry: {entry['subtype']}")
    
    def _create_default_agent_configs(self, session: Session):
        """Create default agent configurations"""
        default_agents = [
            {
                "agent_type": "seo_campaign_manager",
                "name": "SEO Campaign Manager",
                "role": "Expert SEO campaign manager specializing in search engine optimization and organic traffic growth",
                "goal": "Analyze and optimize SEO campaigns to improve organic search rankings and traffic",
                "backstory": "I am an experienced SEO specialist with deep knowledge of search algorithms, keyword research, and content optimization strategies.",
                "task": "Analyze the current SEO performance for {customer_name} and provide actionable recommendations to improve organic search visibility and rankings.",
                "allow_delegation": True,
                "verbose": True,
                "is_active": True,
                "tools": '["google_analytics_tool", "google_search_console_tool", "keyword_research_tool"]',
                "capabilities": '{"data_sources": ["google_analytics", "google_search_console"], "specializations": ["seo", "organic_traffic", "keyword_optimization"]}'
            },
            {
                "agent_type": "social_media_specialist",
                "name": "Social Media Specialist",
                "role": "Social media marketing expert focused on Facebook, Instagram, and other social platforms",
                "goal": "Optimize social media campaigns to increase engagement, reach, and conversions",
                "backstory": "I specialize in social media marketing with expertise in Facebook Ads, Instagram marketing, and social media analytics.",
                "task": "Review social media performance for {customer_name} and provide strategies to improve engagement and ROI on social platforms.",
                "allow_delegation": True,
                "verbose": True,
                "is_active": True,
                "tools": '["facebook_ads_tool", "instagram_analytics_tool", "social_media_tool"]',
                "capabilities": '{"data_sources": ["facebook_ads", "instagram"], "specializations": ["social_media", "paid_social", "engagement"]}'
            },
            {
                "agent_type": "ppc_specialist",
                "name": "PPC Specialist",
                "role": "Pay-per-click advertising expert specializing in Google Ads and other PPC platforms",
                "goal": "Optimize PPC campaigns to maximize ROI and minimize cost per acquisition",
                "backstory": "I am a PPC expert with extensive experience in Google Ads, keyword optimization, and conversion tracking.",
                "task": "Analyze PPC campaign performance for {customer_name} and provide recommendations to improve ad performance and reduce costs.",
                "allow_delegation": True,
                "verbose": True,
                "is_active": True,
                "tools": '["google_ads_tool", "conversion_tracking_tool", "keyword_planner_tool"]',
                "capabilities": '{"data_sources": ["google_ads"], "specializations": ["ppc", "paid_search", "conversion_optimization"]}'
            }
        ]
        
        for agent_data in default_agents:
            # Check if agent already exists
            existing = session.exec(
                select(AgentConfig).where(AgentConfig.agent_type == agent_data["agent_type"])
            ).first()
            
            if not existing:
                agent_config = AgentConfig(**agent_data)
                session.add(agent_config)
                logger.info(f"Created agent config: {agent_data['name']}")
    
    def _create_default_kpi_settings(self, session: Session, customer_id: int, agency_id: int, campaigner_id: int):
        """Create customer-specific KPI settings from default templates"""
        composite_id = f"{agency_id}_{campaigner_id}_{customer_id}"
        
        # Get all default KPI settings (no is_active filter)
        default_settings = session.exec(
            select(DefaultKpiSettings)
        ).all()
        
        if not default_settings:
            logger.warning(f"No default KPI settings found for customer {customer_id}")
            return
        
        # Create customer-specific KPI settings from defaults
        for default_setting in default_settings:
            # Check if this KPI setting already exists for this customer
            existing = session.exec(
                select(KpiSettings).where(
                    and_(
                        KpiSettings.customer_id == customer_id,
                        KpiSettings.campaign_objective == default_setting.campaign_objective,
                        KpiSettings.kpi_name == default_setting.kpi_name,
                        KpiSettings.kpi_type == default_setting.kpi_type
                    )
                )
            ).first()
            
            if not existing:
                customer_kpi = KpiSettings(
                    composite_id=composite_id,
                    customer_id=customer_id,
                    campaign_objective=default_setting.campaign_objective,
                    kpi_name=default_setting.kpi_name,
                    kpi_type=default_setting.kpi_type,
                    direction=default_setting.direction,
                    default_value=default_setting.default_value,
                    unit=default_setting.unit
                )
                session.add(customer_kpi)
                logger.info(f"Created KPI setting for customer {customer_id}: {default_setting.kpi_name}")
        
        logger.info(f"Created default KPI settings for customer {customer_id}")
    
    
    def _create_default_questions(self, session: Session, customer_id: int, agency_id: int, campaigner_id: int):
        """Create default questions for a customer"""
        composite_id = f"{agency_id}_{campaigner_id}_{customer_id}"
        
        # Check if questions already exist
        existing = session.exec(
            select(QuestionsTable).where(QuestionsTable.composite_id == composite_id)
        ).first()
        
        if existing:
            # Update existing questions with defaults
            for i, question in enumerate(self.default_questions[:10], 1):
                setattr(existing, f"q{i}", question)
        else:
            # Create new questions entry
            questions_data = {"composite_id": composite_id}
            for i, question in enumerate(self.default_questions[:10], 1):
                questions_data[f"q{i}"] = question
            
            questions_entry = QuestionsTable(**questions_data)
            session.add(questions_entry)
        
        logger.info(f"Created default questions for customer {customer_id}")
    
    def _create_default_rtm_links(self, session: Session, customer_id: int, agency_id: int, campaigner_id: int):
        """Create default RTM links for a customer"""
        composite_id = f"{agency_id}_{campaigner_id}_{customer_id}"
        
        # Check if RTM entry already exists
        existing = session.exec(
            select(RTMTable).where(RTMTable.composite_id == composite_id)
        ).first()
        
        if existing:
            # Update existing RTM with default links
            existing.link_1 = "https://analytics.google.com"
            existing.link_2 = "https://ads.google.com"
            existing.link_3 = "https://business.facebook.com"
            existing.link_4 = "https://search.google.com/search-console"
        else:
            # Create new RTM entry
            rtm_data = {
                "composite_id": composite_id,
                "link_1": "https://analytics.google.com",
                "link_2": "https://ads.google.com",
                "link_3": "https://business.facebook.com",
                "link_4": "https://search.google.com/search-console"
            }
            
            rtm_entry = RTMTable(**rtm_data)
            session.add(rtm_entry)
        
        logger.info(f"Created default RTM links for customer {customer_id}")
    


# Global instance
default_data_service = DefaultDataService()
