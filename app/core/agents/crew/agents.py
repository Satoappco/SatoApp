"""Agent definitions for the analytics crew."""

from crewai import Agent
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from typing import List, Optional
import os

from app.services.agent_service import AgentService

class AnalyticsAgents:
    """Factory for creating analytics crew agents."""

    def __init__(self, llm: Optional[BaseChatModel] = None):
        self.llm = llm or ChatOpenAI(
            model="gpt-4o",
            temperature=0.3,
            api_key=os.getenv("OPENAI_API_KEY")
        )


    agents_service =  AgentService()
        
    def create_master_agent(self) -> Agent:
        """Create the master orchestrator agent."""

        master_agent_data = self.agents_service.get_agent_config("seo_campaign_manager")

        return Agent(
            role=master_agent_data['role'],
            # "Analytics Master Orchestrator",
            goal=master_agent_data['goal'],
            # "Coordinate data collection from specialists and synthesize comprehensive insights",
            backstory= master_agent_data['backstory'],
            # """You are an expert data analyst with 15+ years of experience in
            # digital marketing analytics. You excel at synthesizing data from multiple
            # sources, identifying patterns, and providing actionable recommendations.
            # You coordinate with platform specialists to gather data and create unified
            # insights that help businesses make data-driven decisions.""",
            reasoning=True,
            max_reasoning_attempts=None,
            inject_date=True,
            verbose=True,
            allow_delegation=True,
            llm=self.llm,
            max_iter=5
        )

    def create_facebook_specialist(self, tools: List) -> Agent:
        """Create the Facebook Ads specialist agent."""
        fb_specialist_data = self.agents_service.get_agent_config("facebook_database_analysis_expert")
        return Agent(
            role=fb_specialist_data['role'],
            # "Facebook Ads Specialist",
            goal=fb_specialist_data['goal'],
            # "Extract, analyze, and provide insights from Facebook Ads data",
            backstory=fb_specialist_data['backstory'],
            # """You are a Facebook Ads expert with deep knowledge of the
            # Facebook Ads platform, campaign optimization, and audience targeting.
            # You understand metrics like CPM, CPC, ROAS, and can identify trends in
            # campaign performance. You use the Facebook Ads MCP server to fetch real-time
            # data and provide detailed analysis of ad performance, audience behavior,
            # and optimization opportunities.""",
            verbose=True,
            inject_date=True,
            allow_delegation=False,
            tools=tools,
            llm=self.llm,
            max_iter=5
        )

    def create_google_specialist(self, tools: List) -> Agent:
        """Create the Google Analytics specialist agent."""
        google_specialist_data = self.agents_service.get_agent_config("google_database_analysis_expert")

        return Agent(
            role=google_specialist_data['role'],
            # "Google Analytics Specialist",
            goal=google_specialist_data['goal'],
            # "Extract, analyze, and provide insights from Google Analytics data",
            backstory=google_specialist_data['backstory'],
            # """You are a Google Analytics expert with comprehensive knowledge
            # of GA4, user behavior analysis, and conversion tracking. You understand
            # metrics like sessions, bounce rate, conversion rate, and user journeys.
            # You use the Google Analytics MCP server to fetch real-time data and provide
            # detailed analysis of website traffic, user behavior, conversion funnels,
            # and content performance. You excel at identifying opportunities for
            # improving user experience and conversion rates.""",
            verbose=True,
            inject_date=True,
            allow_delegation=False,
            tools=tools,
            llm=self.llm,
            max_iter=5
        )
