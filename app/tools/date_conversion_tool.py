"""
Date Conversion Tool for CrewAI agents
This tool PROMPTS the LLM to convert natural language timeframes to exact dates
NO HARDCODED LOGIC - the LLM figures out the dates itself
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from datetime import datetime


class DateConversionInput(BaseModel):
    """Input schema for date conversion"""
    timeframe: str = Field(description="Natural language timeframe like 'last week', 'yesterday', 'October 2023', 'Q1 2024'")


class DateConversionTool(BaseTool):
    """Tool that prompts the LLM to convert natural language timeframes to exact dates"""
    
    name: str = "DateConversionTool"
    description: str = """Convert natural language timeframes to precise YYYY-MM-DD date formats.
    
    This tool helps you understand what dates the user is asking about.
    You MUST think through the date logic yourself and return the exact dates.
    
    Today's date is: {current_date}
    
    Examples:
    - "last week" → Calculate the previous Monday to Sunday from today
    - "yesterday" → Calculate yesterday's date from today
    - "October 2023" → Return 2023-10-01 to 2023-10-31
    - "Q1 2024" → Return 2024-01-01 to 2024-03-31
    - "last 30 days" → Calculate 30 days before today
    
    CRITICAL: You MUST return the result in this EXACT format:
    Start Date: YYYY-MM-DD
    End Date: YYYY-MM-DD
    
    Think through the logic step by step, then return the dates in the exact format above."""
    
    args_schema: type[BaseModel] = DateConversionInput
    
    def _run(self, timeframe: str) -> str:
        """
        This tool doesn't do the conversion - it just returns a prompt for the LLM
        to figure out the dates itself
        """
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        return f"""CRITICAL: Convert the timeframe "{timeframe}" to exact dates.

TODAY'S DATE IS: {current_date}
CURRENT YEAR: {datetime.now().year}
CURRENT MONTH: {datetime.now().strftime('%B')} ({datetime.now().month})
CURRENT DAY: {datetime.now().day}

Think through this step by step:
1. What does "{timeframe}" mean relative to TODAY ({current_date})?
2. Calculate the start date in YYYY-MM-DD format
3. Calculate the end date in YYYY-MM-DD format

IMPORTANT: 
- "last week" means the 7 days BEFORE this week (Monday to Sunday of the previous week)
- Always use {datetime.now().year} as the year for relative dates unless specified otherwise
- Count backwards/forwards from {current_date}

Return ONLY this format (no other text):
Start Date: YYYY-MM-DD
End Date: YYYY-MM-DD

Example for "last week" when today is 2025-10-03 (Thursday):
- Current week started on Monday 2025-09-30
- Last week was Monday 2025-09-23 to Sunday 2025-09-29
- Answer: Start Date: 2025-09-23, End Date: 2025-09-29"""
