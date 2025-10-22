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

        metrics = ", ".join(task_details.get("metrics", []))
        date_range = task_details.get("date_range", {})
        campaigns = task_details.get("specific_campaigns")

        campaign_filter = ""
        if campaigns:
            campaign_filter = f"\nFocus on these specific campaigns: {', '.join(campaigns)}"

        description = f"""Analyze Facebook Ads data for the following:

Time Period: {date_range.get('start')} to {date_range.get('end')}
Metrics: {metrics}{campaign_filter}

Your tasks:
1. Fetch the relevant data from Facebook Ads using the MCP tools
2. Calculate key performance indicators
3. Identify trends and patterns in the data
4. Compare performance across campaigns (if applicable)
5. Identify top-performing and under-performing campaigns
6. Provide specific insights about audience engagement
7. Highlight any anomalies or significant changes

Deliver a structured analysis with:
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
            agent=agent
        )

    @staticmethod
    def create_google_analysis_task(
        agent: Agent,
        task_details: Dict[str, Any]
    ) -> Task:
        """Create a Google Analytics analysis task."""

        metrics = ", ".join(task_details.get("metrics", []))
        date_range = task_details.get("date_range", {})

        description = f"""Analyze Google Analytics data for the following:

Time Period: {date_range.get('start')} to {date_range.get('end')}
Metrics: {metrics}

Your tasks:
1. Fetch the relevant data from Google Analytics using the MCP tools
2. Calculate key performance indicators
3. Analyze user behavior and traffic patterns
4. Examine conversion funnels and drop-off points
5. Identify top traffic sources and landing pages
6. Analyze user demographics and device usage
7. Highlight any significant changes or trends

Deliver a structured analysis with:
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
            agent=agent
        )

    @staticmethod
    def create_synthesis_task(
        agent: Agent,
        task_details: Dict[str, Any],
        context: List[Task]
    ) -> Task:
        """Create a synthesis task for the master agent."""

        platforms = ", ".join(task_details.get("platforms", []))

        description = f"""Synthesize the analytics data from {platforms} into a unified report.

Your tasks:
1. Review the analyses from the platform specialists
2. Identify cross-platform patterns and correlations
3. Synthesize insights from multiple data sources
4. Calculate overall marketing performance metrics
5. Identify opportunities for cross-platform optimization
6. Prioritize recommendations based on potential impact
7. Create an executive summary

Deliver a comprehensive report with:
- Executive summary (2-3 paragraphs)
- Cross-platform insights
- Unified recommendations prioritized by impact
- Overall marketing health assessment
- Next steps and action items
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
            context=context  # This task depends on specialist tasks
        )
