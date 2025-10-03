"""
Date Conversion Tool for CrewAI agents
This tool PROMPTS the LLM to convert natural language timeframes to exact dates
NO HARDCODED LOGIC - the LLM figures out the dates itself
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from crewai_tools import BaseTool
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
        
        return f"""You need to convert the timeframe "{timeframe}" to exact dates.

Today's date is: {current_date}

Think through this step by step:
1. What does "{timeframe}" mean relative to {current_date}?
2. What is the start date in YYYY-MM-DD format?
3. What is the end date in YYYY-MM-DD format?

Return your answer in this EXACT format:
Start Date: YYYY-MM-DD
End Date: YYYY-MM-DD

Think carefully about calendar logic (weekdays, month lengths, leap years, etc.)"""
