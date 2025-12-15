"""
QA Testing Script for Chat API

This script processes a Google Sheets or Excel table with predefined questions and evaluates chat responses.
Columns: type, question, expected_answer, current_answer, previous_answer, rank, suggestion, chat_trace_link, log_link

Process:
1. Move current_answer to previous_answer (unless --fill-blanks is used)
2. Call chat route for each question using JWT authentication (without reusing thread_id)
3. Save response in current_answer (or only fill blanks if --fill-blanks is used)
4. Capture thread_id and generate chat trace and log links
5. Use LLM to rank: "both good", "previous better", "current better", "both bad"
6. Generate suggestions for improvement

Features:
- Supports both Google Sheets URLs and local Excel files
- Fail-fast mode: Stop processing a group when one question fails (enabled by default)
- Groups questions by "Type" column for fail-fast behavior
- Uses QATestingService for core functionality

Authentication:
- Uses JWT tokens for authentication (not API_TOKEN)
- Automatically generates a test JWT token if none provided
- Can also use JWT_TOKEN environment variable or --jwt-token argument

Google Sheets Setup:
- Requires GOOGLE_SHEETS_SERVICE_ACCOUNT_PATH environment variable pointing to service account JSON
- Default sheet: https://docs.google.com/spreadsheets/d/1Trpy3H_VvfZfHPky-f47ilwU714kmrem2kWETibECeM/edit?gid=2126514740#gid=2126514740
"""

import os
import sys
import json
import asyncio
import argparse
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import pandas as pd
import httpx
from dotenv import load_dotenv

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import get_settings
from app.services.qa_service import QATestingService

# Load environment variables
load_dotenv()


class QATestingScript:
    """QA Testing script for evaluating chat responses."""

    def __init__(
        self,
        sheet_url: str = "https://docs.google.com/spreadsheets/d/1Trpy3H_VvfZfHPky-f47ilwU714kmrem2kWETibECeM/edit?gid=2126514740#gid=2126514740",
        api_base_url: str = "http://localhost:8080",
        jwt_token: Optional[str] = None,
        llm_provider: str = "gemini",
        fail_fast: bool = True,
        sheet_name: str = "Automated",
        save_local: bool = False,
        max_concurrent: int = 5,
    ):
        """
        Initialize the QA testing script.

        Args:
            sheet_url: Google Sheets URL or path to Excel file with test cases
            api_base_url: Base URL for the API
            jwt_token: JWT token for authentication
            llm_provider: LLM provider for ranking ("gemini" or "openai")
            fail_fast: If True, stop processing a group when one question fails
            sheet_name: Name of the Google Sheets tab to use (default: "Automated")
            save_local: If True, save results to local Excel file in reports/ directory instead of remote sheet
            max_concurrent: Maximum number of concurrent API calls (default: 5)
        """
        self.sheet_url = sheet_url
        self.api_base_url = api_base_url.rstrip("/")
        self.jwt_token = jwt_token
        self.llm_provider = llm_provider
        self.fail_fast = fail_fast
        self.sheet_name = sheet_name
        self.save_local = save_local
        self.max_concurrent = max_concurrent
        self.settings = get_settings()

        # Set up logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize QA service
        self.qa_service = QATestingService(api_base_url=self.api_base_url)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        """Async context manager exit - cleanup resources."""
        return False

    async def run(
        self,
        start_row: int = 0,
        end_row: Optional[int] = None,
        customer_name: Optional[str] = None,
        fill_blanks: bool = False,
    ):
        """
        Run the complete QA testing workflow.

        Args:
            start_row: Starting row index (0-based)
            end_row: Ending row index (exclusive), None for all rows
            customer_name: Optional customer name to convert to ID
            fill_blanks: If True, only fill rows where Current Answer is blank
        """
        self.logger.info("=" * 80)
        self.logger.info("QA Testing Script for Chat API")
        self.logger.info("=" * 80)

        # Use the QA service to run the tests
        async with self.qa_service:
            results = await self.qa_service.run_qa_test(
                sheet_url=self.sheet_url,
                jwt_token=self.jwt_token,
                customer_name=customer_name,
                start_row=start_row,
                end_row=end_row,
                sheet_name=self.sheet_name,
                fail_fast=self.fail_fast,
                max_concurrent=self.max_concurrent,
                fill_blanks=fill_blanks,
                save_local=self.save_local,
            )

        # Print summary
        self.logger.info("=" * 80)
        self.logger.info("SUMMARY")
        self.logger.info("=" * 80)

        rank_counts = results.get("ranking_distribution", {})
        self.logger.info("Ranking Distribution:")
        for rank, count in rank_counts.items():
            self.logger.info(f"  {rank}: {count}")

        save_location = results.get("save_location", self.sheet_url)
        self.logger.info(f"Testing complete! Results saved to: {save_location}")
        self.logger.info("=" * 80)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="QA Testing Script for Chat API")
    parser.add_argument(
        "sheet_url",
        nargs="?",
        default="https://docs.google.com/spreadsheets/d/1Trpy3H_VvfZfHPky-f47ilwU714kmrem2kWETibECeM/edit?gid=2126514740#gid=2126514740",
        help="Google Sheets URL or path to Excel file with test cases (default: Sato QA sheet)",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8080",
        help="API base URL (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--jwt-token", help="JWT authentication token (can also use JWT_TOKEN env var)"
    )
    parser.add_argument(
        "--customer-name",
        type=str,
        default="AEF",
        help="Customer name to convert to ID for all requests (default: AEF)",
    )
    parser.add_argument(
        "--campaigner-email",
        type=str,
        default="dor.yashar@gmail.com",
        help="Campaigner Email for JWT token (default: dor.yashar@gmail.com)",
    )
    parser.add_argument(
        "--start-row",
        type=int,
        default=0,
        help="Starting row index (0-based, default: 0)",
    )
    parser.add_argument(
        "--end-row", type=int, help="Ending row index (exclusive, default: all rows)"
    )
    parser.add_argument(
        "--llm-provider",
        choices=["gemini"],
        default="gemini",
        help="LLM provider for ranking (default: gemini)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=True,
        help="Stop processing a group when one question fails (default: enabled)",
    )
    parser.add_argument(
        "--no-fail-fast",
        action="store_false",
        dest="fail_fast",
        help="Process all questions regardless of failures",
    )
    parser.add_argument(
        "--sheet-name",
        default="Automated",
        help="Name of the Google Sheets tab to use (default: 'Automated')",
    )
    parser.add_argument(
        "--save-local",
        action="store_true",
        help="Save results to local Excel file in reports/ directory instead of remote sheet",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum number of concurrent API calls (default: 5)",
    )
    parser.add_argument(
        "--fill-blanks",
        action="store_true",
        help="Only fill answers where current_answer is blank (preserves existing current answers)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set the logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )

    # Get JWT token from args or environment
    jwt_token = args.jwt_token or os.getenv("JWT_TOKEN")

    if not jwt_token:
        logger = logging.getLogger(__name__)
        logger.info("No JWT token provided, generating one for testing...")
        try:
            # Import here to avoid circular imports
            from app.core.auth import create_access_token
            from datetime import datetime, timedelta, timezone

            jwt_token = create_access_token(
                data={
                    "type": "access",
                    "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
                    "campaigner_id": args.campaigner_email,
                    # "user_id": 10,
                }
            )
            logger.info(f"Generated JWT token: {jwt_token[:5]}...{jwt_token[-5:]}")
        except Exception as e:
            logger.error(f"Failed to generate JWT token: {e}")
            logger.error("Set JWT_TOKEN env var or use --jwt-token")
            logger.error(
                "You can generate one manually with: python scripts/generate_test_token.py"
            )
            return
    else:
        logger = logging.getLogger(__name__)
        logger.info(f"Using JWT token: {jwt_token[:5]}...{jwt_token[-5:]}")

    # Run the script
    async with QATestingScript(
        sheet_url=args.sheet_url,
        api_base_url=args.api_url,
        jwt_token=jwt_token,
        llm_provider=args.llm_provider,
        fail_fast=args.fail_fast,
        sheet_name=args.sheet_name,
        save_local=args.save_local,
        max_concurrent=args.max_concurrent,
    ) as script:
        await script.run(
            start_row=args.start_row,
            end_row=args.end_row,
            customer_name=args.customer_name,
            fill_blanks=args.fill_blanks,
        )


if __name__ == "__main__":
    asyncio.run(main())
