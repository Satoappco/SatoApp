"""
QA Testing Script for Chat API

This script processes a Google Sheets or Excel table with predefined questions and evaluates chat responses.
Columns: type, question, expected_answer, current_answer, previous_answer, rank, suggestion, chat_trace_link, log_link

Process:
1. Move current_answer to previous_answer
2. Call chat route for each question using JWT authentication (without reusing thread_id)
3. Save response in current_answer
4. Capture thread_id and generate chat trace and log links
5. Use LLM to rank: "both good", "previous better", "current better", "both bad"
6. Generate suggestions for improvement

Features:
- Supports both Google Sheets URLs and local Excel files
- Fail-fast mode: Stop processing a group when one question fails (enabled by default)
- Groups questions by "Type" column for fail-fast behavior

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
        self.is_google_sheets = self._is_google_sheets_url(sheet_url)
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

        # Initialize HTTP client
        self.client = httpx.AsyncClient(timeout=120.0)

        # Semaphore for concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Column names
        self.columns = [
            "Type",
            "Question",
            "Expected Answer",
            "Current Answer",
            "Previous Answer",
            "Rank",
            "Suggestion",
            "Chat Trace Link",
            "Log Link",
        ]

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        """Async context manager exit - cleanup resources."""
        await self.client.aclose()
        return False

    def load_data(self) -> pd.DataFrame:
        """Load data from Google Sheets or Excel file."""
        if self.is_google_sheets:
            return self._load_google_sheets()
        else:
            return self._load_excel()

    def _load_excel(self) -> pd.DataFrame:
        """Load data from Excel file."""
        df = pd.read_excel(self.sheet_url)

        # Validate required columns
        required_columns = ["Question", "Expected Answer"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Add missing optional columns
        for col in self.columns:
            if col not in df.columns:
                df[col] = ""

        return df

    def _is_google_sheets_url(self, url: str) -> bool:
        """Check if the provided URL is a Google Sheets URL."""
        return "docs.google.com/spreadsheets" in url

    def _extract_sheet_id_and_gid(self, url: str) -> tuple[str, str]:
        """Extract spreadsheet ID and sheet GID from Google Sheets URL."""
        # Extract spreadsheet ID
        sheet_id_match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
        if not sheet_id_match:
            raise ValueError("Invalid Google Sheets URL: cannot extract spreadsheet ID")
        sheet_id = sheet_id_match.group(1)

        # Extract GID (sheet ID within the spreadsheet)
        gid_match = re.search(r"gid=(\d+)", url)
        gid = gid_match.group(1) if gid_match else "0"  # Default to first sheet

        return sheet_id, gid

    def _get_gsheets_client(self):
        """Get authenticated gspread client using OAuth2 or service account."""
        # Try OAuth2 first
        client = self._get_oauth2_client()
        if client:
            return client

        # Fall back to service account
        return self._get_service_account_client()

    def _get_oauth2_client(self):
        """Get gspread client using OAuth2 refresh token."""
        try:
            client_id = os.getenv("GOOGLE_SHEETS_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_SHEETS_CLIENT_SECRET")
            refresh_token = os.getenv("GOOGLE_SHEETS_REFRESH_TOKEN")

            if not all([client_id, client_secret, refresh_token]):
                return None

            # Use the existing token refresh function
            from app.core.oauth.token_refresh import refresh_google_token

            assert refresh_token is not None  # Already checked above
            token_data = refresh_google_token(refresh_token)
            access_token = token_data.get("access_token")

            if not access_token:
                self.logger.error("Failed to refresh Google Sheets OAuth2 token")
                return None

            creds = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ],
            )

            return gspread.authorize(creds)

        except Exception as e:
            self.logger.error(f"OAuth2 authentication failed: {e}")
            return None

    def _get_service_account_client(self):
        """Get gspread client using service account JSON file or env var."""
        try:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ]

            # Try to get credentials from JSON string in env var first (for CI/CD)
            json_str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
            if json_str:
                import tempfile

                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False
                ) as f:
                    f.write(json_str)
                    temp_path = f.name
                try:
                    creds = ServiceAccountCredentials.from_json_keyfile_name(
                        temp_path, scope
                    )
                    return gspread.authorize(creds)
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)

            # Fall back to file path
            creds_path = self.settings.google_sheets_service_account_path or os.getenv(
                "GOOGLE_SERVICE_ACCOUNT_PATH"
            )
            if not creds_path:
                return None

            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
            return gspread.authorize(creds)

        except Exception as e:
            self.logger.error(f"Service account authentication failed: {e}")
            return None

    def _load_google_sheets(self) -> pd.DataFrame:
        """Load data from Google Sheets."""
        if not GSHEETS_AVAILABLE:
            raise ImportError(
                "gspread library not available. Install with: pip install gspread oauth2client google-auth"
            )

        sheet_id, gid = self._extract_sheet_id_and_gid(self.sheet_url)

        # Try OAuth2 first, then service account
        client = self._get_gsheets_client()
        if not client:
            raise ValueError(
                "Google Sheets authentication failed. Configure either:\n"
                "  OAuth2: Set GOOGLE_SHEETS_CLIENT_ID, GOOGLE_SHEETS_CLIENT_SECRET, and GOOGLE_SHEETS_REFRESH_TOKEN\n"
                "  Service Account: Set GOOGLE_SHEETS_SERVICE_ACCOUNT_PATH or GOOGLE_SERVICE_ACCOUNT_PATH"
            )

        # Open the spreadsheet and worksheet
        spreadsheet = client.open_by_key(sheet_id)
        if self.sheet_name:
            worksheet = spreadsheet.worksheet(self.sheet_name)
        else:
            worksheet = spreadsheet.get_worksheet_by_id(int(gid))

        # Get all values
        data = worksheet.get_all_records()

        df = pd.DataFrame(data)

        # Validate required columns
        required_columns = ["Question", "Expected Answer"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Add missing optional columns
        for col in self.columns:
            if col not in df.columns:
                df[col] = ""

        return df

    def save_data(self, df: pd.DataFrame):
        """Save the updated DataFrame to Google Sheets, Excel, or local reports directory."""
        if self.save_local:
            self._save_local_reports(df)
        elif self.is_google_sheets:
            self._save_google_sheets(df)
        else:
            self._save_excel(df)

    def _save_excel(self, df: pd.DataFrame):
        """Save the updated DataFrame to Excel."""
        # Create backup before overwriting
        if os.path.exists(self.sheet_url):
            backup_path = (
                f"{self.sheet_url}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            os.rename(self.sheet_url, backup_path)
            self.logger.info(f"Created backup: {backup_path}")

        df.to_excel(self.sheet_url, index=False)
        self.logger.info(f"Saved results to: {self.sheet_url}")

    def _save_local_reports(self, df: pd.DataFrame):
        """Save data to local Excel file in reports directory with timestamp."""
        # Create reports directory if it doesn't exist
        # Path(__file__) is scripts/qa_testing_script.py, so parent.parent is the sato-be directory
        reports_dir = Path(__file__).parent.parent / "reports"
        reports_dir.mkdir(exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"qa_results_{timestamp}.xlsx"
        filepath = reports_dir / filename

        # Save to Excel
        df.to_excel(filepath, index=False)
        self.logger.info(f"Saved results to local file: {filepath}")

    def _save_google_sheets(self, df: pd.DataFrame):
        """Save data to Google Sheets."""
        if not GSHEETS_AVAILABLE:
            raise ImportError(
                "gspread library not available. Install with: pip install gspread oauth2client google-auth"
            )

        sheet_id, gid = self._extract_sheet_id_and_gid(self.sheet_url)

        # Get authenticated client
        client = self._get_gsheets_client()
        if not client:
            raise ValueError(
                "Google Sheets authentication failed. Configure either:\n"
                "  OAuth2: Set GOOGLE_SHEETS_CLIENT_ID, GOOGLE_SHEETS_CLIENT_SECRET, and GOOGLE_SHEETS_REFRESH_TOKEN\n"
                "  Service Account: Set GOOGLE_SHEETS_SERVICE_ACCOUNT_PATH or GOOGLE_SERVICE_ACCOUNT_PATH"
            )

        # Open the spreadsheet and worksheet
        spreadsheet = client.open_by_key(sheet_id)
        if self.sheet_name:
            worksheet = spreadsheet.worksheet(self.sheet_name)
        else:
            worksheet = spreadsheet.get_worksheet_by_id(int(gid))

        # Clear existing data and update with new data
        worksheet.clear()
        worksheet.update([df.columns.tolist()] + df.values.tolist())

        self.logger.info(f"Saved results to Google Sheets: {self.sheet_url}")

    def move_current_to_previous(self, df: pd.DataFrame) -> pd.DataFrame:
        """Move current_answer to previous_answer for all rows."""
        df["Previous Answer"] = df["Current Answer"]
        df["Current Answer"] = ""
        self.logger.info("Moved current answers to previous")
        return df

    async def fetch_customers(self) -> Dict[str, str]:
        """
        Fetch all customers from the API and return a mapping of customer names to IDs.

        Returns:
            Dictionary mapping customer names to customer IDs
        """
        url = f"{self.api_base_url}/api/v1/customers"

        headers = {"Content-Type": "application/json"}

        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"

        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Extract customers from the response
            customers = data.get("customers", [])

            # Create mapping from customer full_name to ID
            customer_map = {}
            for customer in customers:
                if (
                    isinstance(customer, dict)
                    and "full_name" in customer
                    and "id" in customer
                ):
                    customer_map[customer["full_name"].strip()] = str(customer["id"])

            self.logger.info(f"Fetched {len(customer_map)} customers")
            return customer_map

        except httpx.HTTPError as e:
            self.logger.error(f"Failed to fetch customers: {str(e)}")
            if hasattr(e, "response") and e.response:
                self.logger.debug(f"Response: {e.response.text}")
            return {}

    async def call_chat_api(
        self, question: str, customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call the chat API with a question.

        Args:
            question: The question to ask
            customer_id: Optional customer ID

        Returns:
            Dictionary with response data
        """
        url = f"{self.api_base_url}/api/v1/chat"

        headers = {"Content-Type": "application/json"}

        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"

        payload = {
            "message": question,
            # Don't include thread_id to ensure fresh conversation each time
        }

        if customer_id:
            payload["customer_id"] = customer_id

        # Debug: Log equivalent curl command
        curl_cmd = f'curl -X POST "{url}" -H "Content-Type: application/json"'
        if self.jwt_token:
            curl_cmd += f' -H "Authorization: Bearer {self.jwt_token[:10]}..."'
        curl_cmd += f" -d '{json.dumps(payload)}'"
        self.logger.debug(f"Equivalent curl: {curl_cmd}")

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            self.logger.error(f"API Error: {str(e)}")
            if hasattr(e, "response") and e.response:
                self.logger.debug(f"Response: {e.response.text}")
            return {"error": str(e), "message": ""}

    def _generate_trace_url(self, thread_id: str) -> str:
        """Generate trace viewer URL for a thread_id."""
        frontend_url = self.settings.frontend_url or "http://localhost:3000"
        return f"{frontend_url}/traces/{thread_id}"

    def _generate_log_url(self, start_time: datetime, end_time: datetime) -> str:
        """Generate URL for fetching logs in the trace timeframe."""
        from datetime import timedelta

        # Add 5 minute buffer before and after
        buffered_start = start_time - timedelta(minutes=5)
        buffered_end = end_time + timedelta(minutes=5)

        # Format as ISO strings
        start_str = buffered_start.isoformat()
        end_str = buffered_end.isoformat()

        # Construct log API URL
        base_url = self.api_base_url
        log_url = f"{base_url}/api/v1/logs/timerange?start_time={start_str}&end_time={end_str}&max_results=5000"

        return log_url

    async def rank_with_llm(
        self,
        question: str,
        expected_answer: str,
        current_answer: str,
        previous_answer: str,
    ) -> Dict[str, str]:
        """
        Use LLM to rank the answers and provide suggestions.

        Args:
            question: The original question
            expected_answer: The expected/ideal answer
            current_answer: The current API response
            previous_answer: The previous API response

        Returns:
            Dictionary with "rank" and "suggestion" keys
        """
        prompt = f"""You are evaluating two AI chatbot responses to determine which is better.

Question: {question}

Expected/Ideal Answer: {expected_answer}

Previous Answer: {previous_answer if previous_answer else "N/A (no previous answer)"}

Current Answer: {current_answer if current_answer else "N/A (no current answer)"}

Task:
1. Compare both answers against the expected answer
2. Provide a ranking using EXACTLY one of these four options:
   - "both good" - Both answers are acceptable and meet expectations
   - "previous better" - The previous answer is superior
   - "current better" - The current answer is superior
   - "both bad" - Neither answer is acceptable

3. Provide a brief suggestion (1-2 sentences) for improvement

Respond in JSON format:
{{
    "rank": "<one of: both good, previous better, current better, both bad>",
    "suggestion": "<brief suggestion for improvement>"
}}
"""

        if self.llm_provider == "gemini":
            return await self._rank_with_gemini(prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    async def _rank_with_gemini(self, prompt: str) -> Dict[str, str]:
        """Use Google Gemini to rank answers."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.settings.gemini_api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")

            response = model.generate_content(prompt)
            result_text = response.text.strip()

            # Try to parse JSON from the response
            # Handle markdown code blocks
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)

            # Validate rank value
            valid_ranks = ["both good", "previous better", "current better", "both bad"]
            if result.get("rank") not in valid_ranks:
                self.logger.warning(
                    f"Invalid rank: {result.get('rank')}, defaulting to 'both bad'"
                )
                result["rank"] = "both bad"

            return result

        except Exception as e:
            self.logger.error(f"LLM Ranking Error: {str(e)}")
            return {"rank": "both bad", "suggestion": f"Error during ranking: {str(e)}"}

    async def process_single_test_case(
        self,
        df: pd.DataFrame,
        idx: int,
        customer_id: Optional[str] = None,
    ) -> tuple[int, str, str, str, str, str]:
        """
        Process a single test case with concurrency control.

        Args:
            df: DataFrame with test cases
            idx: Row index to process
            customer_id: Optional customer ID

        Returns:
            Tuple of (idx, current_answer, rank, suggestion, trace_link, log_link)
        """
        async with self.semaphore:
            row = df.loc[idx]
            question = row["Question"]
            expected_answer = row["Expected Answer"]
            previous_answer = row["Previous Answer"]

            self.logger.info(f"[{idx + 1}] Testing: {question[:60]}...")

            # Call chat API and capture start time
            start_time = datetime.now()
            self.logger.debug(f"  → Calling chat API...")
            response = await self.call_chat_api(question, customer_id)
            end_time = datetime.now()

            current_answer = response.get("message", "")
            thread_id = response.get("thread_id", "")

            # Generate trace and log URLs
            trace_link = ""
            log_link = ""
            if thread_id:
                trace_link = self._generate_trace_url(thread_id)
                log_link = self._generate_log_url(start_time, end_time)
                self.logger.debug(f"  🔗 Trace: {trace_link}")

            if response.get("error"):
                current_answer = f"ERROR: {response['error']}"

            self.logger.info(f"  ✅ Got response: {current_answer[:100]}...")

            # Rank with LLM
            self.logger.debug(f"  → Ranking with LLM...")
            ranking = await self.rank_with_llm(
                question=question,
                expected_answer=expected_answer,
                current_answer=current_answer,
                previous_answer=previous_answer,
            )

            rank = ranking.get("rank", "both bad")
            suggestion = ranking.get("suggestion", "")

            self.logger.info(f"  ✅ Rank: {rank}")
            self.logger.debug(f"  💡 Suggestion: {suggestion[:80]}...")
            self.logger.debug("")

            return idx, current_answer, rank, suggestion, trace_link, log_link

    async def process_test_cases(
        self,
        df: pd.DataFrame,
        start_row: int = 0,
        end_row: Optional[int] = None,
        customer_id: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Process test cases from the DataFrame.

        Args:
            df: DataFrame with test cases
            start_row: Starting row index (0-based)
            end_row: Ending row index (exclusive), None for all rows
            customer_id: Optional customer ID to use for all requests

        Returns:
            Updated DataFrame
        """
        end_row = end_row or len(df)
        total_rows = end_row - start_row

        self.logger.info(
            f"Processing {total_rows} test cases (rows {start_row} to {end_row - 1})..."
        )

        # Group by Type if fail_fast is enabled
        if self.fail_fast and "Group" in df.columns:
            # Process by groups sequentially (fail_fast within group)
            grouped = df.iloc[start_row:end_row].groupby("Group", sort=False)
            for group_name, group_df in grouped:
                self.logger.info(f"Processing group: {group_name}")
                group_failed = False

                for idx in group_df.index:
                    if group_failed:
                        self.logger.info(
                            f"Skipping remaining questions in group '{group_name}' due to previous failure"
                        )
                        break

                    # Process single test case
                    (
                        idx,
                        current_answer,
                        rank,
                        suggestion,
                        trace_link,
                        log_link,
                    ) = await self.process_single_test_case(df, idx, customer_id)

                    df.at[idx, "Current Answer"] = current_answer
                    df.at[idx, "Rank"] = rank
                    df.at[idx, "Suggestion"] = suggestion
                    df.at[idx, "Chat Trace Link"] = trace_link
                    df.at[idx, "Log Link"] = log_link

                    # Check if this question failed and fail_fast is enabled
                    if self.fail_fast and rank in ["previous better", "both bad"]:
                        group_failed = True
                        self.logger.warning(
                            f"Question failed with rank '{rank}', skipping remaining questions in group '{group_name}'"
                        )
        else:
            # Process all rows in parallel with concurrency limit
            self.logger.info(
                f"Processing {total_rows} test cases in parallel (max {self.max_concurrent} concurrent)..."
            )

            tasks = [
                self.process_single_test_case(df, idx, customer_id)
                for idx in range(start_row, end_row)
            ]

            # Execute all tasks in parallel with concurrency control
            results = await asyncio.gather(*tasks)

            # Update DataFrame with results
            for idx, current_answer, rank, suggestion, trace_link, log_link in results:
                df.at[idx, "Current Answer"] = current_answer
                df.at[idx, "Rank"] = rank
                df.at[idx, "Suggestion"] = suggestion
                df.at[idx, "Chat Trace Link"] = trace_link
                df.at[idx, "Log Link"] = log_link

        # Save progress after processing
        self.save_data(df)

        return df

    async def run(
        self,
        start_row: int = 0,
        end_row: Optional[int] = None,
        customer_name: Optional[str] = None,
    ):
        """
        Run the complete QA testing workflow.

        Args:
            start_row: Starting row index (0-based)
            end_row: Ending row index (exclusive), None for all rows
            customer_name: Optional customer name to convert to ID
        """
        self.logger.info("=" * 80)
        self.logger.info("QA Testing Script for Chat API")
        self.logger.info("=" * 80)

        # Convert customer_name to customer_id if provided
        customer_id = None
        customer_name = customer_name.strip()
        if customer_name:
            self.logger.info(f"Converting customer name '{customer_name}' to ID...")
            customer_map = await self.fetch_customers()
            if customer_name in customer_map:
                customer_id = customer_map[customer_name]
                self.logger.info(f"Found customer ID: {customer_id}")
            else:
                self.logger.warning(
                    f"Customer name '{customer_name}' not found in available customers"
                )
                self.logger.info(f"Available customers: {list(customer_map.keys())}")

        # Load data
        source_type = "Google Sheets" if self.is_google_sheets else "Excel file"
        self.logger.info(f"Loading {source_type}: {self.sheet_url}")
        df = self.load_data()
        self.logger.info(f"Loaded {len(df)} test cases")

        # Move current to previous
        self.logger.info(f"Moving current answers to previous...")
        df = self.move_current_to_previous(df)
        self.save_data(df)

        # Process test cases
        df = await self.process_test_cases(df, start_row, end_row, customer_id)

        # Final save
        self.save_data(df)

        # Print summary
        self.logger.info("=" * 80)
        self.logger.info("SUMMARY")
        self.logger.info("=" * 80)

        rank_counts = df["Rank"].value_counts()
        self.logger.info("Ranking Distribution:")
        for rank, count in rank_counts.items():
            self.logger.info(f"  {rank}: {count}")

        save_location = "local reports directory" if self.save_local else self.sheet_url
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
        )


if __name__ == "__main__":
    asyncio.run(main())
