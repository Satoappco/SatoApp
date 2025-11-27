"""Task definitions for the analytics crew."""

from crewai import Task, Agent
from typing import Dict, Any, List


class AnalyticsTasks:
    """Factory for creating analytics crew tasks."""

    @staticmethod
    def create_facebook_analysis_task(
        agent: Agent, task_details: Dict[str, Any]
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
            campaign_filter = (
                f"\nFocus on these specific campaigns: {', '.join(campaigns)}"
            )

        description = f"""User Question: {query}

{context_info}

Analyze Facebook Ads data for the following:

Time Period: {date_range.get("start")} to {date_range.get("end")}
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
"""
        # - Data formatted as JSON with structured insights
        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            async_execution=True,  # Will be executed asynchronously
        )

    @staticmethod
    def create_google_analysis_task(agent: Agent, task_details: Dict[str, Any]) -> Task:
        """Create a Google Analytics analysis task."""

        query = task_details.get("query", "")
        context = task_details.get("context", {})
        metrics = ", ".join(task_details.get("metrics", []))
        date_range = task_details.get("date_range", {})

        # Get Google Analytics credentials with property ID
        ga_credentials = task_details.get("google_analytics_credentials", {})
        ga_credentials = ga_credentials or {}
        property_id = ga_credentials.get("property_id", "NOT_PROVIDED")

        # Get Google Ads credentials with customer ID
        gads_credentials = task_details.get("google_ads_credentials", {})
        gads_credentials = gads_credentials or {}
        customer_id = gads_credentials.get("customer_id", "NOT_PROVIDED")
        account_id = gads_credentials.get("account_id", "NOT_PROVIDED")

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

        if property_id and property_id != "NOT_PROVIDED":
            context_info += (
                f"\n\nGoogle Analytics Property:\n- Property ID: {property_id}"
            )
        if account_id and account_id != "NOT_PROVIDED":
            context_info += f"\n\nGoogle Ads Account:\n- Account ID: {account_id}"
        if customer_id and customer_id != "NOT_PROVIDED":
            context_info += f"\n- Customer ID: {customer_id}"

        description = f"""User Question: {query}

{context_info}

Analyze Google Analytics and/or Google Ads data for the following:

Time Period: {date_range.get("start")} to {date_range.get("end")}
Metrics: {metrics}

IMPORTANT: Use the Property ID when querying Google Analytics data through MCP tools.
IMPORTANT: Use the Customer ID when querying Google Ads data through MCP tools.

Your tasks:
1. Understand the user's question and what specific insights they need
2. Use the Property ID to fetch the relevant data from Google Analytics using the MCP tools.
3. Use the Customer ID / Account ID to fetch Google Ads data if needed.
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
"""
        # - Data formatted as JSON with structured insights

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            async_execution=True,  # Will be executed asynchronously
        )

    @staticmethod
    def create_synthesis_task(
        agent: Agent, task_details: Dict[str, Any], context: List[Task]
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
"""
        # - Data formatted as structured JSON
        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            async_execution=False,  # Synthesis task must be synchronous (final task)
            context=context,  # This task depends on specialist tasks
        )

    @staticmethod
    def create_merged_task(agent: Agent, task_details: Dict[str, Any]) -> Task:
        """Create a merged task that handles all platforms in one unified analysis."""

        query = task_details.get("query", "")
        context = task_details.get("context", {})
        metrics = ", ".join(task_details.get("metrics", []))
        date_range = task_details.get("date_range", {})
        platforms = task_details.get("platforms", [])

        # Get all credentials
        fb_credentials = task_details.get("meta_ads_credentials", {}) or {}
        ad_account_id = fb_credentials.get("ad_account_id", "NOT_PROVIDED")

        ga_credentials = task_details.get("google_analytics_credentials", {}) or {}
        property_id = ga_credentials.get("property_id", "NOT_PROVIDED")

        gads_credentials = task_details.get("google_ads_credentials", {}) or {}
        customer_id = gads_credentials.get("customer_id", "NOT_PROVIDED")
        account_id = gads_credentials.get("account_id", "NOT_PROVIDED")

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

        # Add account information for all platforms
        if ad_account_id and ad_account_id != "NOT_PROVIDED":
            context_info += (
                f"\n\nFacebook Ads Account:\n- Ad Account ID: {ad_account_id}"
            )

        if property_id and property_id != "NOT_PROVIDED":
            context_info += (
                f"\n\nGoogle Analytics Property:\n- Property ID: {property_id}"
            )

        if account_id and account_id != "NOT_PROVIDED":
            context_info += f"\n\nGoogle Ads Account:\n- Account ID: {account_id}"
        if customer_id and customer_id != "NOT_PROVIDED":
            context_info += f"\n- Customer ID: {customer_id}"

        # Determine which platforms to analyze
        platform_list = []
        if "facebook" in platforms or "facebook_ads" in platforms:
            platform_list.append("Facebook Ads")
        if "google_analytics" in platforms:
            platform_list.append("Google Analytics")
        if "google_ads" in platforms:
            platform_list.append("Google Ads")

        platforms_str = (
            ", ".join(platform_list) if platform_list else "all available platforms"
        )

        description = f"""User Question: {query}

{context_info}

Perform a comprehensive unified analysis across {platforms_str} for the following:

Time Period: {date_range.get("start")} to {date_range.get("end")}
Metrics: {metrics}

IMPORTANT: Use the appropriate account/credential IDs provided above when querying each platform's data through MCP tools.

Your comprehensive tasks across all platforms:
1. Understand the user's question and what specific insights they need
2. For Facebook Ads: Use Ad Account ID to fetch campaign data, calculate KPIs, identify trends, and analyze audience engagement
3. For Google Analytics: Use Property ID to analyze user behavior, traffic patterns, conversion funnels, and demographics
4. For Google Ads: Use Customer/Account ID to analyze campaign performance, ad spend efficiency, and conversion tracking
5. Calculate unified key performance indicators across all platforms
6. Identify cross-platform patterns and correlations
7. Compare performance across different marketing channels
8. Analyze user journey from awareness (ads) to conversion (analytics)
9. Identify top-performing and under-performing campaigns/channels
10. Highlight anomalies and significant changes across platforms
11. Provide actionable insights that span multiple platforms
12. Answer the user's specific question with data from all relevant sources

Deliver a comprehensive unified analysis with:
- Direct answer to the user's question (first and foremost)
- Executive summary covering all platforms (2-3 paragraphs)
- Cross-platform performance comparison
- Unified metrics dashboard
- User journey analysis (ads → analytics)
- Channel attribution insights
- Actionable recommendations (at least 5, prioritized by impact)
- Specific optimization strategies for each platform
- Overall marketing health assessment
- Next steps and prioritized action items

IMPORTANT: Make sure your response is in {context.get("language", "english")} language.
"""

        expected_output = """A comprehensive unified analytics report including:
- Executive summary covering all platforms
- Cross-platform performance metrics and comparisons
- User journey analysis from ads to conversions
- Channel attribution and ROI analysis
- 5+ prioritized actionable insights and recommendations
- Platform-specific optimization strategies
- Marketing performance scorecard
- Detailed action plan with timelines
"""
        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            async_execution=True,  # Can be executed asynchronously
        )
