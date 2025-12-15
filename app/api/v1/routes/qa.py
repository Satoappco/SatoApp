"""QA Testing API routes."""

import uuid
from datetime import datetime
from typing import Dict, Any
import asyncio
import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from app.api.schemas.qa import QATestRequest, QATestResponse, QAJobStatus
from app.api.dependencies import get_app_state, ApplicationState
from app.core.auth import get_current_user
from app.config.settings import get_settings
from app.models.users import Campaigner
from app.services.qa_service import QATestingService

router = APIRouter(prefix="/qa", tags=["qa-testing"])
logger = logging.getLogger(__name__)

# Simple in-memory job store (in production, use Redis or database)
qa_jobs: Dict[str, Dict[str, Any]] = {}


@router.post("/test", response_model=QATestResponse)
async def start_qa_test(
    request: QATestRequest,
    background_tasks: BackgroundTasks,
    current_user: Campaigner = Depends(get_current_user),
):
    """
    Start a QA testing job.

    This endpoint initiates QA testing against the chat API using questions from
    Google Sheets or Excel files. The testing process runs asynchronously in the background.
    """
    job_id = str(uuid.uuid4())

    # Initialize job status
    qa_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "message": "Job queued for processing",
        "progress": None,
        "results": None,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "completed_at": None,
    }

    # Start background task
    settings = get_settings()
    background_tasks.add_task(
        run_qa_test_background,
        job_id,
        request,
        f"http://{settings.host}:{settings.port}",
    )

    return QATestResponse(
        job_id=job_id,
        status="pending",
        message="QA testing job started",
        total_rows=None,
        processed_rows=None,
        created_at=qa_jobs[job_id]["created_at"],
    )

    return QATestResponse(
        job_id=job_id,
        status="pending",
        message="QA testing job started",
        created_at=qa_jobs[job_id]["created_at"],
    )


@router.get("/test/{job_id}", response_model=QAJobStatus)
async def get_qa_test_status(
    job_id: str,
    current_user: Campaigner = Depends(get_current_user),
):
    """Get the status of a QA testing job."""
    if job_id not in qa_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = qa_jobs[job_id]
    return QAJobStatus(**job)


async def run_qa_test_background(
    job_id: str, request: QATestRequest, api_base_url: str
):
    """Run QA testing in the background."""
    try:
        # Update job status to running
        qa_jobs[job_id].update(
            {
                "status": "running",
                "message": "Initializing QA testing...",
                "updated_at": datetime.now(),
            }
        )

        # Generate JWT token for testing
        from app.core.auth import create_access_token
        from datetime import timedelta, timezone

        jwt_token = create_access_token(
            data={
                "type": "access",
                "exp": datetime.now(timezone.utc)
                + timedelta(minutes=60),  # Longer for testing
                "campaigner_id": getattr(
                    request, "campaigner_email", "test@example.com"
                ),
            }
        )

        # Initialize QA service
        async with QATestingService(api_base_url=api_base_url) as qa_service:
            # Update progress
            qa_jobs[job_id]["message"] = "Loading test data..."
            qa_jobs[job_id]["updated_at"] = datetime.now()

            # Run the QA test
            results = await qa_service.run_qa_test(
                sheet_url=request.sheet_url,
                jwt_token=jwt_token,
                customer_name=request.customer_name,
                start_row=request.start_row,
                end_row=request.end_row,
                sheet_name=request.sheet_name,
                fail_fast=request.fail_fast,
                max_concurrent=request.max_concurrent,
                fill_blanks=request.fill_blanks,
                save_local=request.save_local,
            )

            # Update job with results
            qa_jobs[job_id].update(
                {
                    "status": "completed",
                    "message": "QA testing completed successfully",
                    "progress": {
                        "total_rows": results.get("total_rows", 0),
                        "processed_rows": results.get("processed_rows", 0),
                    },
                    "results": results,
                    "updated_at": datetime.now(),
                    "completed_at": datetime.now(),
                }
            )

    except Exception as e:
        logger.error(f"QA test job {job_id} failed: {str(e)}")
        qa_jobs[job_id].update(
            {
                "status": "failed",
                "message": f"QA testing failed: {str(e)}",
                "updated_at": datetime.now(),
                "completed_at": datetime.now(),
            }
        )


__all__ = ["router"]
