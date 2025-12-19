"""
Weekly Review Workflow using LangGraph.

This workflow conducts weekly reviews of work plan progress including:
1. Progress assessment
2. Blockers identification
3. Performance trends analysis
4. Recommendations adjustments
5. Health scoring
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


class WeeklyReviewWorkflow:
    """LangGraph workflow for weekly work plan reviews."""

    def __init__(self, model_name: str = "gpt-4o"):
        """Initialize the weekly review workflow."""
        self.llm = ChatOpenAI(model=model_name, temperature=0.2)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the review workflow graph."""
        workflow = StateGraph(dict)

        # Add nodes
        workflow.add_node("assess_progress", self.assess_progress)
        workflow.add_node("identify_blockers", self.identify_blockers)
        workflow.add_node("analyze_trends", self.analyze_trends)
        workflow.add_node("generate_adjustments", self.generate_adjustments)
        workflow.add_node("calculate_health", self.calculate_health)

        # Define edges
        workflow.set_entry_point("assess_progress")
        workflow.add_edge("assess_progress", "identify_blockers")
        workflow.add_edge("identify_blockers", "analyze_trends")
        workflow.add_edge("analyze_trends", "generate_adjustments")
        workflow.add_edge("generate_adjustments", "calculate_health")
        workflow.add_edge("calculate_health", END)

        return workflow.compile()

    async def assess_progress(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Assess progress on completed and in-progress tasks."""
        logger.info("Assessing weekly progress")

        tasks = state.get("tasks", [])
        week_number = state.get("week_number", 1)

        prompt = f"""You are a project manager reviewing weekly progress. Analyze the following tasks for week {week_number}:

{self._format_tasks(tasks)}

Assess the progress and identify:
1. Key achievements (tasks completed or major progress made)
2. Tasks in progress
3. Tasks not started yet
4. Overall progress percentage (0-100)

Format your response as JSON with keys: achievements (array of strings), in_progress (array of strings), not_started (array of strings), progress_percentage (number)."""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])

            import json
            assessment = json.loads(response.content)

            return {
                **state,
                "progress_assessment": assessment,
                "tokens_used": state.get("tokens_used", 0) + response.response_metadata.get("token_usage", {}).get("total_tokens", 0)
            }
        except Exception as e:
            logger.error(f"Error in progress assessment: {str(e)}")
            return {
                **state,
                "progress_assessment": {"error": str(e)},
                "errors": state.get("errors", []) + [f"Progress assessment failed: {str(e)}"]
            }

    async def identify_blockers(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Identify blockers and risks."""
        logger.info("Identifying blockers")

        tasks = state.get("tasks", [])
        progress = state.get("progress_assessment", {})

        prompt = f"""You are a risk manager. Based on the current task status, identify:

Tasks in Progress: {progress.get('in_progress', [])}
Tasks Not Started: {progress.get('not_started', [])}

All Tasks:
{self._format_tasks(tasks)}

Identify:
1. Blockers (specific issues preventing task completion)
2. Risks (potential problems that might occur)
3. Opportunities (unexpected positive developments)

For each, provide:
- Title
- Description
- Severity (high/medium/low)
- Recommended action

Format as JSON with keys: blockers (array), risks (array), opportunities (array)."""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])

            import json
            blockers_data = json.loads(response.content)

            return {
                **state,
                "blockers": blockers_data.get("blockers", []),
                "risks": blockers_data.get("risks", []),
                "opportunities": blockers_data.get("opportunities", []),
                "tokens_used": state.get("tokens_used", 0) + response.response_metadata.get("token_usage", {}).get("total_tokens", 0)
            }
        except Exception as e:
            logger.error(f"Error identifying blockers: {str(e)}")
            return {
                **state,
                "blockers": [],
                "risks": [],
                "opportunities": [],
                "errors": state.get("errors", []) + [f"Blocker identification failed: {str(e)}"]
            }

    async def analyze_trends(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance trends."""
        logger.info("Analyzing trends")

        metrics = state.get("metrics_snapshot", {})
        week_number = state.get("week_number", 1)

        prompt = f"""You are a data analyst. Analyze the performance trends for week {week_number}:

Current Metrics:
{json.dumps(metrics, indent=2)}

Progress: {state.get('progress_assessment', {}).get('progress_percentage', 0)}%
Completed Tasks: {len([t for t in state.get('tasks', []) if t.get('status') == 'completed'])}
Total Tasks: {len(state.get('tasks', []))}

Calculate:
1. Progress velocity (tasks completed per week)
2. Trend direction (improving/stable/declining)
3. Key insights (notable patterns or changes)

Format as JSON with keys: progress_velocity (number), trend_direction (string), insights (array of strings)."""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])

            import json
            trends = json.loads(response.content)

            return {
                **state,
                "progress_velocity": trends.get("progress_velocity", 0),
                "trend_direction": trends.get("trend_direction", "stable"),
                "insights": trends.get("insights", []),
                "tokens_used": state.get("tokens_used", 0) + response.response_metadata.get("token_usage", {}).get("total_tokens", 0)
            }
        except Exception as e:
            logger.error(f"Error analyzing trends: {str(e)}")
            return {
                **state,
                "progress_velocity": 0,
                "trend_direction": "unknown",
                "insights": [],
                "errors": state.get("errors", []) + [f"Trend analysis failed: {str(e)}"]
            }

    async def generate_adjustments(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommended adjustments."""
        logger.info("Generating adjustments")

        blockers = state.get("blockers", [])
        risks = state.get("risks", [])
        opportunities = state.get("opportunities", [])

        prompt = f"""You are a strategy consultant. Based on the weekly review, recommend adjustments:

Blockers: {json.dumps(blockers, indent=2)}
Risks: {json.dumps(risks, indent=2)}
Opportunities: {json.dumps(opportunities, indent=2)}

Generate:
1. New Recommendations (actions to take based on findings)
2. Task Adjustments (changes to existing tasks - reprioritize, add, remove, modify)

Each should include:
- Title
- Description
- Priority (high/medium/low)
- Type (new_task/modify_task/remove_task/reprioritize)

Format as JSON with keys: new_recommendations (array), task_adjustments (array)."""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])

            import json
            adjustments = json.loads(response.content)

            return {
                **state,
                "new_recommendations": adjustments.get("new_recommendations", []),
                "task_adjustments": adjustments.get("task_adjustments", []),
                "tokens_used": state.get("tokens_used", 0) + response.response_metadata.get("token_usage", {}).get("total_tokens", 0)
            }
        except Exception as e:
            logger.error(f"Error generating adjustments: {str(e)}")
            return {
                **state,
                "new_recommendations": [],
                "task_adjustments": [],
                "errors": state.get("errors", []) + [f"Adjustments generation failed: {str(e)}"]
            }

    async def calculate_health(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall health score."""
        logger.info("Calculating health score")

        # Calculate health score based on multiple factors
        progress_pct = state.get("progress_assessment", {}).get("progress_percentage", 0)
        num_blockers = len(state.get("blockers", []))
        num_risks = len([r for r in state.get("risks", []) if r.get("severity") == "high"])
        trend = state.get("trend_direction", "stable")

        # Health score formula
        health_score = progress_pct

        # Penalties
        health_score -= (num_blockers * 5)  # -5 per blocker
        health_score -= (num_risks * 10)  # -10 per high-risk item

        # Trend adjustments
        if trend == "improving":
            health_score += 10
        elif trend == "declining":
            health_score -= 10

        # Clamp to 0-100
        health_score = max(0, min(100, health_score))

        return {
            **state,
            "overall_health_score": float(health_score)
        }

    def _format_tasks(self, tasks: List[Dict[str, Any]]) -> str:
        """Format tasks for LLM prompt."""
        if not tasks:
            return "No tasks"

        formatted = []
        for task in tasks:
            formatted.append(
                f"- {task.get('title', 'Untitled')} "
                f"({task.get('status', 'pending')}) "
                f"[Priority: {task.get('priority', 'N/A')}, "
                f"Impact: {task.get('impact', 'N/A')}]"
            )
        return "\n".join(formatted)

    async def execute(
        self,
        week_number: int,
        tasks: List[Dict[str, Any]],
        metrics_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the weekly review workflow.

        Args:
            week_number: Current week number
            tasks: List of tasks for the week
            metrics_snapshot: Current performance metrics

        Returns:
            Complete review results
        """
        logger.info(f"Executing weekly review for week {week_number}")

        initial_state = {
            "week_number": week_number,
            "tasks": tasks,
            "metrics_snapshot": metrics_snapshot,
            "tokens_used": 0,
            "errors": []
        }

        final_state = await self.graph.ainvoke(initial_state)

        # Generate markdown report
        markdown_report = self._generate_markdown_report(final_state)

        return {
            "achievements": final_state.get("progress_assessment", {}).get("achievements", []),
            "blockers": final_state.get("blockers", []),
            "risks": final_state.get("risks", []),
            "opportunities": final_state.get("opportunities", []),
            "new_recommendations": final_state.get("new_recommendations", []),
            "task_adjustments": final_state.get("task_adjustments", []),
            "overall_health_score": final_state.get("overall_health_score", 50.0),
            "progress_velocity": final_state.get("progress_velocity", 0),
            "full_review_markdown": markdown_report,
            "tokens_used": final_state.get("tokens_used", 0),
            "errors": final_state.get("errors", [])
        }

    def _generate_markdown_report(self, state: Dict[str, Any]) -> str:
        """Generate markdown report for the weekly review."""
        import json

        week_number = state.get("week_number", 1)
        assessment = state.get("progress_assessment", {})

        report = f"""# Weekly Review - Week {week_number}

**Date**: {datetime.utcnow().strftime('%Y-%m-%d')}
**Overall Health Score**: {state.get('overall_health_score', 0):.1f}/100
**Progress Velocity**: {state.get('progress_velocity', 0):.2f} tasks/week
**Trend**: {state.get('trend_direction', 'Unknown').capitalize()}

---

## Progress Summary

**Overall Progress**: {assessment.get('progress_percentage', 0)}%

### Achievements ✅
"""

        for achievement in assessment.get("achievements", []):
            report += f"- {achievement}\n"

        report += "\n### Tasks In Progress 🔄\n"
        for task in assessment.get("in_progress", []):
            report += f"- {task}\n"

        report += "\n### Tasks Not Started ⏳\n"
        for task in assessment.get("not_started", []):
            report += f"- {task}\n"

        report += "\n---\n\n## Blockers & Risks\n\n### Blockers 🚧\n"
        for blocker in state.get("blockers", []):
            report += f"""
**{blocker.get('title', 'Blocker')}** (Severity: {blocker.get('severity', 'N/A')})
{blocker.get('description', '')}
*Recommended Action*: {blocker.get('recommended_action', 'N/A')}

"""

        report += "### Risks ⚠️\n"
        for risk in state.get("risks", []):
            report += f"""
**{risk.get('title', 'Risk')}** (Severity: {risk.get('severity', 'N/A')})
{risk.get('description', '')}
*Recommended Action*: {risk.get('recommended_action', 'N/A')}

"""

        report += "### Opportunities 🌟\n"
        for opp in state.get("opportunities", []):
            report += f"""
**{opp.get('title', 'Opportunity')}** (Severity: {opp.get('severity', 'N/A')})
{opp.get('description', '')}
*Recommended Action*: {opp.get('recommended_action', 'N/A')}

"""

        report += "---\n\n## Recommendations\n\n"
        for rec in state.get("new_recommendations", []):
            report += f"""
### {rec.get('title', 'Recommendation')}
{rec.get('description', '')}

- **Priority**: {rec.get('priority', 'N/A')}
- **Type**: {rec.get('type', 'N/A')}

"""

        report += "---\n\n## Task Adjustments\n\n"
        for adj in state.get("task_adjustments", []):
            report += f"""
### {adj.get('title', 'Adjustment')}
{adj.get('description', '')}

- **Priority**: {adj.get('priority', 'N/A')}
- **Type**: {adj.get('type', 'N/A')}

"""

        report += f"""
---

## Review Metadata

- **Tokens Used**: {state.get('tokens_used', 0)}
- **Insights**: {len(state.get('insights', []))}

"""

        if state.get("insights"):
            report += "\n### Key Insights\n"
            for insight in state.get("insights", []):
                report += f"- {insight}\n"

        errors = state.get("errors", [])
        if errors:
            report += "\n### Errors\n"
            for error in errors:
                report += f"- {error}\n"

        report += "\n---\n\n*This review was automatically generated.*\n"

        return report


# Singleton instance
_weekly_review_workflow = None

def get_weekly_review_workflow(model_name: str = "gpt-4o") -> WeeklyReviewWorkflow:
    """Get or create the weekly review workflow instance."""
    global _weekly_review_workflow
    if _weekly_review_workflow is None:
        _weekly_review_workflow = WeeklyReviewWorkflow(model_name=model_name)
    return _weekly_review_workflow
