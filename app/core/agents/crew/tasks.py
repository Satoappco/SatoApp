"""Task definitions for the analytics crew."""

from crewai import Task, Agent
from typing import Dict, Any, List


class AnalyticsTasks:
    """Factory for creating analytics crew tasks."""

    @staticmethod
    def create_facebook_analysis_task(
        agent: Agent,
        task_details: Dict[str, Any]
    ) -> Task:
        """Create a Facebook Ads analysis task."""

        query = task_details.get("query", "")
        context = task_details.get("context", {})
        metrics = ", ".join(task_details.get("metrics", []))
        date_range = task_details.get("date_range", {})
        campaigns = task_details.get("specific_campaigns")

        # Get Facebook credentials with ad account ID
        fb_credentials = task_details.get("meta_ads_credentials", {})
        ad_account_id = fb_credentials.get("ad_account_id", "NOT_PROVIDED")

        # Build context information
        context_info = ""
        if context:
            agency = context.get("agency", {})
            campaigner = context.get("campaigner", {})
            language = context.get("language", "english")

            if agency:
                context_info += f"\n\nAgency Context:\n- Name: {agency.get('name')}"
            if campaigner:
                context_info += f"\n\nCampaigner Context:\n- Name: {campaigner.get('full_name')}\n- Email: {campaigner.get('email')}"
            context_info += f"\n\nResponse Language: {language}"

        # Add account information
        context_info += f"\n\nFacebook Ads Account:\n- Ad Account ID: {ad_account_id}"

        campaign_filter = ""
        if campaigns:
            campaign_filter = f"\nFocus on these specific campaigns: {', '.join(campaigns)}"

        description = f"""User Question: {query}

{context_info}

Analyze Facebook Ads data for the following:

Time Period: {date_range.get('start')} to {date_range.get('end')}
Metrics: {metrics}{campaign_filter}

IMPORTANT: Use the Ad Account ID provided above when querying Facebook Ads data through MCP tools.

Your tasks:
1. Understand the user's question and what specific insights they need
2. Use the Ad Account ID ({ad_account_id}) to fetch the relevant data from Facebook Ads using the MCP tools
3. Calculate key performance indicators
4. Identify trends and patterns in the data
5. Compare performance across campaigns (if applicable)
6. Identify top-performing and under-performing campaigns
7. Provide specific insights about audience engagement
8. Highlight any anomalies or significant changes
9. Answer the user's specific question

Deliver a structured analysis with:
- Direct answer to the user's question
- Key metrics summary
- Performance trends
- Actionable insights (at least 3)
- Specific recommendations for optimization
"""

        expected_output = """A comprehensive Facebook Ads analysis including:
- Metrics summary (impressions, clicks, conversions, spend, ROAS)
- Campaign performance comparison
- Audience insights
- 3-5 actionable insights with recommendations
- Data formatted as JSON with structured insights"""

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            async_execution=True # Will be executed asynchronously
        )

    @staticmethod
    def create_google_analysis_task(
        agent: Agent,
        task_details: Dict[str, Any]
    ) -> Task:
        """Create a Google Analytics analysis task."""

        query = task_details.get("query", "")
        context = task_details.get("context", {})
        metrics = ", ".join(task_details.get("metrics", []))
        date_range = task_details.get("date_range", {})

        # Get Google Analytics credentials with property ID
        ga_credentials = task_details.get("google_analytics_credentials", {})
        property_id = ga_credentials.get("property_id", "NOT_PROVIDED")

        # Get Google Ads credentials with customer ID
        gads_credentials = task_details.get("google_ads_credentials", {})
        customer_id = gads_credentials.get("customer_id", "NOT_PROVIDED")

        # Build context information
        context_info = ""
        if context:
            agency = context.get("agency", {})
            campaigner = context.get("campaigner", {})
            language = context.get("language", "english")

            if agency:
                context_info += f"\n\nAgency Context:\n- Name: {agency.get('name')}"
            if campaigner:
                context_info += f"\n\nCampaigner Context:\n- Name: {campaigner.get('full_name')}\n- Email: {campaigner.get('email')}"
            context_info += f"\n\nResponse Language: {language}"

        # Add account information
        context_info += f"\n\nGoogle Analytics Property:\n- Property ID: {property_id}"
        if customer_id != "NOT_PROVIDED":
            context_info += f"\n\nGoogle Ads Account:\n- Customer ID: {customer_id}"

        description = f"""User Question: {query}

{context_info}

Analyze Google Analytics and/or Google Ads data for the following:

Time Period: {date_range.get('start')} to {date_range.get('end')}
Metrics: {metrics}

IMPORTANT: Use the Property ID ({property_id}) when querying Google Analytics data through MCP tools.
{f'IMPORTANT: Use the Customer ID ({customer_id}) when querying Google Ads data through MCP tools.' if customer_id != 'NOT_PROVIDED' else ''}

Your tasks:
1. Understand the user's question and what specific insights they need
2. Use the Property ID ({property_id}) to fetch the relevant data from Google Analytics using the MCP tools
{f'3. Use the Customer ID ({customer_id}) to fetch Google Ads data if needed' if customer_id != 'NOT_PROVIDED' else '3. Focus on Google Analytics data'}
4. Calculate key performance indicators
5. Analyze user behavior and traffic patterns
6. Examine conversion funnels and drop-off points
7. Identify top traffic sources and landing pages
8. Analyze user demographics and device usage
9. Highlight any significant changes or trends
10. Answer the user's specific question

Deliver a structured analysis with:
- Direct answer to the user's question
- Key metrics summary
- Traffic and behavior trends
- Conversion funnel analysis
- Actionable insights (at least 3)
- Specific recommendations for optimization
"""

        expected_output = """A comprehensive Google Analytics analysis including:
- Metrics summary (sessions, users, bounce rate, conversions)
- Traffic source breakdown
- User behavior insights
- Conversion funnel analysis
- 3-5 actionable insights with recommendations
- Data formatted as JSON with structured insights"""

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            async_execution=True # Will be executed asynchronously
        )

    @staticmethod
    def create_synthesis_task(
        agent: Agent,
        task_details: Dict[str, Any],
        context: List[Task]
    ) -> Task:
        """Create a synthesis task for the master agent."""

        query = task_details.get("query", "")
        task_context = task_details.get("context", {})
        platforms = ", ".join(task_details.get("platforms", []))

        # Build context information
        context_info = ""
        if task_context:
            agency = task_context.get("agency", {})
            campaigner = task_context.get("campaigner", {})
            language = task_context.get("language", "english")

            if agency:
                context_info += f"\n\nAgency Context:\n- Name: {agency.get('name')}"
            if campaigner:
                context_info += f"\n\nCampaigner Context:\n- Name: {campaigner.get('full_name')}\n- Email: {campaigner.get('email')}"
            context_info += f"\n\nIMPORTANT: Respond in {language} language"

        description = f"""User Question: {query}

{context_info}

Synthesize the analytics data from {platforms} into a unified report that directly answers the user's question.

Your tasks:
1. Understand what the user is specifically asking for
2. Review the analyses from the platform specialists
3. Extract the information that directly answers the user's question
4. Identify cross-platform patterns and correlations
5. Synthesize insights from multiple data sources
6. Calculate overall marketing performance metrics
7. Identify opportunities for cross-platform optimization
8. Prioritize recommendations based on potential impact
9. Create an executive summary that answers the user's question

Deliver a comprehensive report with:
- Direct answer to the user's question (first and foremost)
- Executive summary (2-3 paragraphs)
- Cross-platform insights
- Unified recommendations prioritized by impact
- Overall marketing health assessment
- Next steps and action items

IMPORTANT: Make sure your response is in {task_context.get("language", "english")} language.
"""

        expected_output = """A synthesized analytics report including:
- Executive summary
- Key findings from all platforms
- Cross-platform insights and correlations
- Prioritized recommendations (top 5)
- Marketing performance scorecard
- Detailed action plan
- Data formatted as structured JSON"""

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            async_execution=False,  # Synthesis task must be synchronous (final task)
            context=context  # This task depends on specialist tasks
        )
