"""
Customer Analysis Workflow using LangGraph.

This workflow orchestrates a comprehensive multi-phase customer analysis including:
1. Client Brief Generation
2. Website Research & Analysis
3. Market Research & Competitor Analysis
4. Digital Campaign Analysis
5. Recommendations & Work Plan Generation
"""

import logging
import json
from typing import Dict, Any, List, TypedDict, Annotated, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from openai import RateLimitError, APIError

logger = logging.getLogger(__name__)


class AnalysisState(TypedDict):
    """State for customer analysis workflow."""
    # Input
    campaigner_id: int
    customer_id: Optional[int]
    campaigner_name: str
    customer_name: Optional[str]
    website_url: Optional[str]
    business_description: Optional[str]

    # Phase outputs
    client_brief: Dict[str, Any]
    website_analysis: Dict[str, Any]
    market_research: Dict[str, Any]
    campaign_analysis: Dict[str, Any]
    recommendations: Dict[str, Any]
    work_plan: Dict[str, Any]

    # Metadata
    current_phase: str
    phase_count: int
    errors: List[str]
    tokens_used: int
    api_calls_made: int


class CustomerAnalysisWorkflow:
    """LangGraph workflow for comprehensive customer analysis."""

    def __init__(
        self,
        model_name: str = "gpt-4o",
        summarization_model_name: str = "gpt-4o-mini"
    ):
        """
        Initialize the customer analysis workflow.

        Args:
            model_name: Primary LLM model for analysis
            summarization_model_name: Model for summarization tasks
        """
        self.llm = ChatOpenAI(model=model_name, temperature=0.2)
        self.summarization_llm = ChatOpenAI(model=summarization_model_name, temperature=0.1)

        # Build the workflow graph
        self.graph = self._build_graph()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _invoke_llm_with_retry(self, messages: List, llm=None) -> Any:
        """
        Invoke LLM with automatic retry on rate limits and API errors.

        Args:
            messages: List of messages to send to LLM
            llm: Optional LLM instance (defaults to self.llm)

        Returns:
            LLM response

        Raises:
            Exception: If all retries are exhausted
        """
        if llm is None:
            llm = self.llm

        return await llm.ainvoke(messages)

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AnalysisState)

        # Add nodes for each phase
        workflow.add_node("generate_client_brief", self.generate_client_brief)
        workflow.add_node("analyze_website", self.analyze_website)
        workflow.add_node("research_market", self.research_market)
        workflow.add_node("analyze_campaigns", self.analyze_campaigns)
        workflow.add_node("generate_recommendations", self.generate_recommendations)
        workflow.add_node("create_work_plan", self.create_work_plan)

        # Define edges (sequential execution)
        workflow.set_entry_point("generate_client_brief")
        workflow.add_edge("generate_client_brief", "analyze_website")
        workflow.add_edge("analyze_website", "research_market")
        workflow.add_edge("research_market", "analyze_campaigns")
        workflow.add_edge("analyze_campaigns", "generate_recommendations")
        workflow.add_edge("generate_recommendations", "create_work_plan")
        workflow.add_edge("create_work_plan", END)

        return workflow.compile()

    async def generate_client_brief(self, state: AnalysisState) -> Dict[str, Any]:
        """
        Phase 1: Generate client brief.

        Analyzes customer information to create a comprehensive brief including:
        - Company overview
        - Industry classification
        - Target audience
        - Unique value proposition
        - Business goals
        """
        logger.info("Phase 1: Generating client brief")

        prompt = f"""You are an expert marketing analyst. Create a comprehensive client brief based on the following information:

Customer: {state.get('customer_name', 'Unknown')}
Website: {state.get('website_url', 'Not provided')}
Business Description: {state.get('business_description', 'Not provided')}

Generate a detailed client brief with the following sections:
1. Company Name
2. Industry Classification
3. Target Audience (demographics, psychographics)
4. Unique Value Proposition
5. Business Goals (inferred from available information)
6. Key Challenges (potential obstacles)

Format your response as JSON with keys: company_name, industry, target_audience, unique_value_proposition, business_goals, key_challenges.
Each value should be a string or array of strings as appropriate."""

        try:
            response = await self._invoke_llm_with_retry([HumanMessage(content=prompt)])

            # Parse response

            client_brief = json.loads(response.content)

            return {
                "client_brief": client_brief,
                "current_phase": "client_brief",
                "phase_count": state.get("phase_count", 0) + 1,
                "tokens_used": state.get("tokens_used", 0) + response.response_metadata.get("token_usage", {}).get("total_tokens", 0),
                "api_calls_made": state.get("api_calls_made", 0) + 1
            }
        except Exception as e:
            logger.error(f"Error in client brief generation: {str(e)}")
            errors = state.get("errors", [])
            errors.append(f"Client brief generation failed: {str(e)}")
            return {
                "client_brief": {"error": str(e)},
                "current_phase": "client_brief",
                "phase_count": state.get("phase_count", 0) + 1,
                "errors": errors
            }

    async def analyze_website(self, state: AnalysisState) -> Dict[str, Any]:
        """
        Phase 2: Website analysis.

        Analyzes the customer's website for:
        - Key pages and structure
        - Products/services offered
        - User experience assessment
        - Technical SEO basics
        """
        logger.info("Phase 2: Analyzing website")

        website_url = state.get("website_url")

        if not website_url:
            return {
                "website_analysis": {
                    "url": None,
                    "key_pages": [],
                    "products_services": [],
                    "user_experience_notes": "No website URL provided",
                    "technical_seo_score": 0
                },
                "current_phase": "website_analysis",
                "phase_count": state.get("phase_count", 0) + 1
            }

        prompt = f"""You are a web analytics expert. Analyze the following website: {website_url}

Based on typical website structures and the client brief provided, infer and suggest:
1. Key Pages (e.g., Home, About, Services, Contact, Blog)
2. Products/Services (based on the industry: {state.get('client_brief', {}).get('industry', 'Unknown')})
3. User Experience Assessment (navigation, mobile-friendliness, speed considerations)
4. Technical SEO Score (0-100, based on best practices)

Client Context:
{json.dumps(state.get('client_brief', {}), indent=2)}

Format your response as JSON with keys: url, key_pages, products_services, user_experience_notes, technical_seo_score."""

        try:
            response = await self._invoke_llm_with_retry([HumanMessage(content=prompt)])


            website_analysis = json.loads(response.content)

            return {
                "website_analysis": website_analysis,
                "current_phase": "website_analysis",
                "phase_count": state.get("phase_count", 0) + 1,
                "tokens_used": state.get("tokens_used", 0) + response.response_metadata.get("token_usage", {}).get("total_tokens", 0),
                "api_calls_made": state.get("api_calls_made", 0) + 1
            }
        except Exception as e:
            logger.error(f"Error in website analysis: {str(e)}")
            errors = state.get("errors", [])
            errors.append(f"Website analysis failed: {str(e)}")
            return {
                "website_analysis": {"error": str(e), "url": website_url},
                "current_phase": "website_analysis",
                "phase_count": state.get("phase_count", 0) + 1,
                "errors": errors
            }

    async def research_market(self, state: AnalysisState) -> Dict[str, Any]:
        """
        Phase 3: Market research.

        Conducts market and competitor research including:
        - Key competitors identification
        - Market size estimation
        - Current trends
        - Opportunities and threats
        """
        logger.info("Phase 3: Researching market")

        client_brief = state.get("client_brief", {})

        prompt = f"""You are a market research analyst. Conduct comprehensive market research for:

Industry: {client_brief.get('industry', 'Unknown')}
Company: {client_brief.get('company_name', 'Unknown')}
Target Audience: {client_brief.get('target_audience', 'Unknown')}

Provide analysis on:
1. Key Competitors (3-5 main competitors in the same industry)
2. Market Size (estimated market value and growth rate)
3. Current Trends (3-5 major industry trends)
4. Opportunities (market gaps and growth areas)
5. Threats (competitive pressures and market challenges)

Format your response as JSON with keys: competitors (array of objects with name, website, strengths), market_size, trends (array of strings), opportunities (array of strings), threats (array of strings)."""

        try:
            response = await self._invoke_llm_with_retry([HumanMessage(content=prompt)])


            market_research = json.loads(response.content)

            return {
                "market_research": market_research,
                "current_phase": "market_research",
                "phase_count": state.get("phase_count", 0) + 1,
                "tokens_used": state.get("tokens_used", 0) + response.response_metadata.get("token_usage", {}).get("total_tokens", 0),
                "api_calls_made": state.get("api_calls_made", 0) + 1
            }
        except Exception as e:
            logger.error(f"Error in market research: {str(e)}")
            errors = state.get("errors", [])
            errors.append(f"Market research failed: {str(e)}")
            return {
                "market_research": {"error": str(e)},
                "current_phase": "market_research",
                "phase_count": state.get("phase_count", 0) + 1,
                "errors": errors
            }

    async def analyze_campaigns(self, state: AnalysisState) -> Dict[str, Any]:
        """
        Phase 4: Digital campaign analysis.

        Analyzes digital marketing campaigns and performance:
        - Active campaigns assessment
        - Performance metrics
        - Key insights
        - Optimization opportunities
        """
        logger.info("Phase 4: Analyzing campaigns")

        # In a real implementation, this would fetch actual campaign data
        # from Google Ads, Facebook Ads, etc. via the respective services

        prompt = f"""You are a digital marketing analyst. Based on the customer profile, suggest typical campaign analysis:

Industry: {state.get('client_brief', {}).get('industry', 'Unknown')}
Business Goals: {state.get('client_brief', {}).get('business_goals', [])}

Provide analysis framework for:
1. Active Campaigns (typical campaign types for this industry)
2. Performance Summary (key metrics to track)
3. Key Metrics (CTR, CPC, ROAS benchmarks for the industry)
4. Recommendations (campaign optimization suggestions)

Format your response as JSON with keys: active_campaigns (array), performance_summary (object), key_metrics (object), recommendations (array of strings)."""

        try:
            response = await self._invoke_llm_with_retry([HumanMessage(content=prompt)])


            campaign_analysis = json.loads(response.content)

            return {
                "campaign_analysis": campaign_analysis,
                "current_phase": "campaign_analysis",
                "phase_count": state.get("phase_count", 0) + 1,
                "tokens_used": state.get("tokens_used", 0) + response.response_metadata.get("token_usage", {}).get("total_tokens", 0),
                "api_calls_made": state.get("api_calls_made", 0) + 1
            }
        except Exception as e:
            logger.error(f"Error in campaign analysis: {str(e)}")
            errors = state.get("errors", [])
            errors.append(f"Campaign analysis failed: {str(e)}")
            return {
                "campaign_analysis": {"error": str(e)},
                "current_phase": "campaign_analysis",
                "phase_count": state.get("phase_count", 0) + 1,
                "errors": errors
            }

    async def generate_recommendations(self, state: AnalysisState) -> Dict[str, Any]:
        """
        Phase 5: Generate recommendations.

        Synthesizes insights from all previous phases to create:
        - Strategic recommendations
        - Tactical recommendations
        - Priority actions
        """
        logger.info("Phase 5: Generating recommendations")

        context = f"""
Client Brief: {json.dumps(state.get('client_brief', {}), indent=2)}
Website Analysis: {json.dumps(state.get('website_analysis', {}), indent=2)}
Market Research: {json.dumps(state.get('market_research', {}), indent=2)}
Campaign Analysis: {json.dumps(state.get('campaign_analysis', {}), indent=2)}
"""

        prompt = f"""You are a senior marketing strategist. Based on the comprehensive analysis, generate recommendations:

{context}

Create three types of recommendations:

1. STRATEGIC (3-5 high-level recommendations for long-term growth)
2. TACTICAL (5-7 specific actions to improve current performance)
3. PRIORITY ACTIONS (Top 3 most urgent actions to take immediately)

Each recommendation should include:
- Title (brief description)
- Description (detailed explanation)
- Expected Impact (high/medium/low)
- Effort Required (high/medium/low)

Format as JSON with keys: strategic (array), tactical (array), priority_actions (array).
Each item should have: title, description, expected_impact, effort_required."""

        try:
            response = await self._invoke_llm_with_retry([HumanMessage(content=prompt)])


            recommendations = json.loads(response.content)

            return {
                "recommendations": recommendations,
                "current_phase": "recommendations",
                "phase_count": state.get("phase_count", 0) + 1,
                "tokens_used": state.get("tokens_used", 0) + response.response_metadata.get("token_usage", {}).get("total_tokens", 0),
                "api_calls_made": state.get("api_calls_made", 0) + 1
            }
        except Exception as e:
            logger.error(f"Error in recommendations generation: {str(e)}")
            errors = state.get("errors", [])
            errors.append(f"Recommendations generation failed: {str(e)}")
            return {
                "recommendations": {"error": str(e)},
                "current_phase": "recommendations",
                "phase_count": state.get("phase_count", 0) + 1,
                "errors": errors
            }

    async def create_work_plan(self, state: AnalysisState) -> Dict[str, Any]:
        """
        Phase 6: Create work plan.

        Creates an 8-week actionable work plan with:
        - Weekly tasks organized by category
        - Priority levels
        - Dependencies
        - Expected impact
        """
        logger.info("Phase 6: Creating work plan")

        recommendations = state.get("recommendations", {})

        prompt = f"""You are a project manager. Create an 8-week work plan based on these recommendations:

Strategic: {json.dumps(recommendations.get('strategic', []), indent=2)}
Tactical: {json.dumps(recommendations.get('tactical', []), indent=2)}
Priority Actions: {json.dumps(recommendations.get('priority_actions', []), indent=2)}

Create a detailed work plan with tasks distributed across 8 weeks:
- Week 1-2: Priority actions and quick wins
- Week 3-4: Core tactical improvements
- Week 5-6: Strategic initiatives begin
- Week 7-8: Optimization and measurement

For each week, provide 2-4 specific tasks with:
- Category (campaign_optimization, content_creation, technical_seo, analytics, strategy, etc.)
- Title
- Description
- Priority (high/medium/low)
- Impact (high/medium/low)
- Effort (high/medium/low)
- Dependencies (array of task titles this depends on, if any)

Format as JSON with keys: period_weeks (8), tasks_by_week.
tasks_by_week should be an object with week_1 through week_8, each containing an array of tasks."""

        try:
            response = await self._invoke_llm_with_retry([HumanMessage(content=prompt)])


            work_plan = json.loads(response.content)

            return {
                "work_plan": work_plan,
                "current_phase": "work_plan",
                "phase_count": state.get("phase_count", 0) + 1,
                "tokens_used": state.get("tokens_used", 0) + response.response_metadata.get("token_usage", {}).get("total_tokens", 0),
                "api_calls_made": state.get("api_calls_made", 0) + 1
            }
        except Exception as e:
            logger.error(f"Error in work plan creation: {str(e)}")
            errors = state.get("errors", [])
            errors.append(f"Work plan creation failed: {str(e)}")
            return {
                "work_plan": {"error": str(e), "period_weeks": 8, "tasks_by_week": {}},
                "current_phase": "work_plan",
                "phase_count": state.get("phase_count", 0) + 1,
                "errors": errors
            }

    async def execute(
        self,
        campaigner_id: int,
        campaigner_name: str,
        customer_id: Optional[int] = None,
        customer_name: Optional[str] = None,
        website_url: Optional[str] = None,
        business_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete customer analysis workflow.

        Args:
            campaigner_id: The campaigner ID
            campaigner_name: The campaigner name
            customer_id: Optional customer ID
            customer_name: Optional customer name
            website_url: Optional website URL
            business_description: Optional business description

        Returns:
            Complete analysis results
        """
        logger.info(f"Executing customer analysis workflow for customer {customer_name}")

        # Initialize state
        initial_state: AnalysisState = {
            "campaigner_id": campaigner_id,
            "customer_id": customer_id,
            "campaigner_name": campaigner_name,
            "customer_name": customer_name,
            "website_url": website_url,
            "business_description": business_description,
            "client_brief": {},
            "website_analysis": {},
            "market_research": {},
            "campaign_analysis": {},
            "recommendations": {},
            "work_plan": {},
            "current_phase": "init",
            "phase_count": 0,
            "errors": [],
            "tokens_used": 0,
            "api_calls_made": 0
        }

        # Execute workflow
        final_state = await self.graph.ainvoke(initial_state)

        return {
            "client_brief": final_state.get("client_brief", {}),
            "website_analysis": final_state.get("website_analysis", {}),
            "market_research": final_state.get("market_research", {}),
            "campaign_analysis": final_state.get("campaign_analysis", {}),
            "recommendations": final_state.get("recommendations", {}),
            "work_plan": final_state.get("work_plan", {}),
            "full_report_markdown": self._generate_markdown_report(final_state),
            "tokens_used": final_state.get("tokens_used", 0),
            "api_calls_made": final_state.get("api_calls_made", 0),
            "phases_completed": final_state.get("phase_count", 0),
            "errors": final_state.get("errors", [])
        }

    def _generate_markdown_report(self, state: AnalysisState) -> str:
        """Generate a comprehensive markdown report from the analysis."""


        report = f"""# Customer Analysis Report

**Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
**Customer**: {state.get('customer_name', 'Unknown')}
**Analyst**: {state.get('campaigner_name', 'Unknown')}

---

## 1. Client Brief

**Company**: {state.get('client_brief', {}).get('company_name', 'N/A')}
**Industry**: {state.get('client_brief', {}).get('industry', 'N/A')}

### Target Audience
{state.get('client_brief', {}).get('target_audience', 'Not specified')}

### Unique Value Proposition
{state.get('client_brief', {}).get('unique_value_proposition', 'Not specified')}

### Business Goals
"""

        goals = state.get('client_brief', {}).get('business_goals', [])
        if isinstance(goals, list):
            for goal in goals:
                report += f"- {goal}\n"
        else:
            report += f"{goals}\n"

        report += f"""
### Key Challenges
"""

        challenges = state.get('client_brief', {}).get('key_challenges', [])
        if isinstance(challenges, list):
            for challenge in challenges:
                report += f"- {challenge}\n"
        else:
            report += f"{challenges}\n"

        report += f"""
---

## 2. Website Analysis

**URL**: {state.get('website_analysis', {}).get('url', 'N/A')}
**Technical SEO Score**: {state.get('website_analysis', {}).get('technical_seo_score', 'N/A')}/100

### Key Pages
"""

        pages = state.get('website_analysis', {}).get('key_pages', [])
        for page in pages:
            if isinstance(page, dict):
                report += f"- **{page.get('name', 'Page')}**: {page.get('description', '')}\n"
            else:
                report += f"- {page}\n"

        report += f"""
### Products/Services
"""

        products = state.get('website_analysis', {}).get('products_services', [])
        for product in products:
            report += f"- {product}\n"

        report += f"""
### User Experience Assessment
{state.get('website_analysis', {}).get('user_experience_notes', 'No assessment available')}

---

## 3. Market Research

### Market Size
{state.get('market_research', {}).get('market_size', 'Not estimated')}

### Key Competitors
"""

        competitors = state.get('market_research', {}).get('competitors', [])
        for comp in competitors:
            if isinstance(comp, dict):
                report += f"- **{comp.get('name', 'Competitor')}** ({comp.get('website', 'N/A')}): {comp.get('strengths', '')}\n"
            else:
                report += f"- {comp}\n"

        report += f"""
### Industry Trends
"""

        trends = state.get('market_research', {}).get('trends', [])
        for trend in trends:
            report += f"- {trend}\n"

        report += f"""
### Opportunities
"""

        opportunities = state.get('market_research', {}).get('opportunities', [])
        for opp in opportunities:
            report += f"- {opp}\n"

        report += f"""
### Threats
"""

        threats = state.get('market_research', {}).get('threats', [])
        for threat in threats:
            report += f"- {threat}\n"

        report += """
---

## 4. Campaign Analysis

### Performance Summary
"""

        perf_summary = state.get('campaign_analysis', {}).get('performance_summary', {})
        for key, value in perf_summary.items():
            report += f"- **{key}**: {value}\n"

        report += """
### Key Metrics
"""

        metrics = state.get('campaign_analysis', {}).get('key_metrics', {})
        for metric, value in metrics.items():
            report += f"- **{metric}**: {value}\n"

        report += """
---

## 5. Recommendations

### Strategic Recommendations
"""

        strategic = state.get('recommendations', {}).get('strategic', [])
        for rec in strategic:
            if isinstance(rec, dict):
                report += f"""
#### {rec.get('title', 'Recommendation')}
{rec.get('description', '')}

- **Expected Impact**: {rec.get('expected_impact', 'N/A')}
- **Effort Required**: {rec.get('effort_required', 'N/A')}
"""

        report += """
### Tactical Recommendations
"""

        tactical = state.get('recommendations', {}).get('tactical', [])
        for rec in tactical:
            if isinstance(rec, dict):
                report += f"""
#### {rec.get('title', 'Recommendation')}
{rec.get('description', '')}

- **Expected Impact**: {rec.get('expected_impact', 'N/A')}
- **Effort Required**: {rec.get('effort_required', 'N/A')}
"""

        report += """
### Priority Actions
"""

        priority = state.get('recommendations', {}).get('priority_actions', [])
        for idx, rec in enumerate(priority, 1):
            if isinstance(rec, dict):
                report += f"""
#### {idx}. {rec.get('title', 'Action')}
{rec.get('description', '')}

- **Expected Impact**: {rec.get('expected_impact', 'N/A')}
- **Effort Required**: {rec.get('effort_required', 'N/A')}
"""

        report += f"""
---

## 6. 8-Week Work Plan

"""

        tasks_by_week = state.get('work_plan', {}).get('tasks_by_week', {})
        for week in range(1, 9):
            week_key = f"week_{week}"
            tasks = tasks_by_week.get(week_key, [])

            if tasks:
                report += f"\n### Week {week}\n\n"
                for task in tasks:
                    if isinstance(task, dict):
                        report += f"""
**{task.get('title', 'Task')}** ({task.get('category', 'general')})

{task.get('description', '')}

- Priority: {task.get('priority', 'N/A')}
- Impact: {task.get('impact', 'N/A')}
- Effort: {task.get('effort', 'N/A')}
"""
                        deps = task.get('dependencies', [])
                        if deps:
                            report += f"- Dependencies: {', '.join(deps)}\n"
                        report += "\n"

        report += f"""
---

## Analysis Metadata

- **Phases Completed**: {state.get('phase_count', 0)}
- **Tokens Used**: {state.get('tokens_used', 0)}
- **API Calls**: {state.get('api_calls_made', 0)}
"""

        errors = state.get('errors', [])
        if errors:
            report += "\n### Errors Encountered\n"
            for error in errors:
                report += f"- {error}\n"

        report += "\n---\n\n*This report was automatically generated by the Customer Analysis Workflow.*\n"

        return report


def get_workflow(
    model_name: str = "gpt-4o",
    summarization_model_name: str = "gpt-4o-mini"
) -> CustomerAnalysisWorkflow:
    """
    Get a new workflow instance with specified models.

    Note: We create a new instance each time to ensure model parameters
    are respected and to avoid thread-safety issues.
    """
    return CustomerAnalysisWorkflow(
        model_name=model_name,
        summarization_model_name=summarization_model_name
    )
