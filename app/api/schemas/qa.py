"""QA Testing API schemas."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class QATestRequest(BaseModel):
    """Request to run QA testing."""

    sheet_url: str = Field(
        ...,
        description="Google Sheets URL or path to Excel file with test cases",
        example="https://docs.google.com/spreadsheets/d/1Trpy3H_VvfZfHPky-f47ilwU714kmrem2kWETibECeM/edit?gid=2126514740#gid=2126514740",
    )
    customer_name: Optional[str] = Field(
        "AEF",
        description="Customer name to convert to ID for all requests",
        example="AEF",
    )
    start_row: int = Field(0, description="Starting row index (0-based)", ge=0)
    end_row: Optional[int] = Field(
        None, description="Ending row index (exclusive), None for all rows", ge=0
    )
    sheet_name: str = Field(
        "Automated",
        description="Name of the Google Sheets tab to use",
        example="Automated",
    )
    fail_fast: bool = Field(
        True, description="Stop processing a group when one question fails"
    )
    max_concurrent: int = Field(
        5, description="Maximum number of concurrent API calls", ge=1, le=20
    )
    fill_blanks: bool = Field(
        False, description="Only fill answers where current_answer is blank"
    )
    save_local: bool = Field(
        False, description="Save results to local Excel file instead of remote sheet"
    )


class QATestResponse(BaseModel):
    """Response from QA testing."""

    job_id: str = Field(..., description="Unique job ID for tracking the QA test run")
    status: str = Field(..., description="Current status of the job", example="running")
    message: str = Field(..., description="Status message")
    total_rows: Optional[int] = Field(
        None, description="Total number of test cases to process"
    )
    processed_rows: Optional[int] = Field(
        None, description="Number of rows processed so far"
    )
    created_at: datetime = Field(..., description="When the job was created")


class QAJobStatus(BaseModel):
    """QA job status response."""

    job_id: str = Field(..., description="Unique job ID")
    status: str = Field(
        ...,
        description="Current status: pending, running, completed, failed",
        example="running",
    )
    message: str = Field(..., description="Status message")
    progress: Optional[Dict[str, Any]] = Field(None, description="Progress information")
    results: Optional[Dict[str, Any]] = Field(
        None, description="Final results when completed"
    )
    created_at: datetime = Field(..., description="When the job was created")
    updated_at: datetime = Field(..., description="When the job was last updated")
    completed_at: Optional[datetime] = Field(None, description="When the job completed")


class QARankingDistribution(BaseModel):
    """Ranking distribution from QA results."""

    both_good: int = Field(0, description="Number of 'both good' rankings")
    previous_better: int = Field(0, description="Number of 'previous better' rankings")
    current_better: int = Field(0, description="Number of 'current better' rankings")
    both_bad: int = Field(0, description="Number of 'both bad' rankings")
