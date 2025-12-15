"""QA Testing Service."""

import os
import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

import pandas as pd
import httpx

from app.config.settings import get_settings
from app.core.auth import create_access_token
from datetime import timedelta, timezone

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False


class QATestingService:
    """Service for running QA tests against chat API."""

    def __init__(self, api_base_url: str = "http://localhost:8080"):
        self.settings = get_settings()
        self.api_base_url = api_base_url.rstrip("/")
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize HTTP client
        self.client = httpx.AsyncClient(timeout=120.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        await self.client.aclose()

    def _is_google_sheets_url(self, url: str) -> bool:
        """Check if the provided URL is a Google Sheets URL."""
        return "docs.google.com/spreadsheets" in url

    def _extract_sheet_id_and_gid(self, url: str) -> tuple[str, str]:
        """Extract spreadsheet ID and sheet GID from Google Sheets URL."""
        import re

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

            creds = Credentials(  # type: ignore
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

            return gspread.authorize(creds)  # type: ignore

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
                    creds = ServiceAccountCredentials.from_json_keyfile_name(  # type: ignore
                        temp_path,
                        scope,  # type: ignore
                    )
                    return gspread.authorize(creds)  # type: ignore
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

            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)  # type: ignore
            return gspread.authorize(creds)  # type: ignore

        except Exception as e:
            self.logger.error(f"Service account authentication failed: {e}")
            return None

    def load_data(self, sheet_url: str, sheet_name: str = "Automated") -> pd.DataFrame:
        """Load data from Google Sheets or Excel file."""
        if self._is_google_sheets_url(sheet_url):
            return self._load_google_sheets(sheet_url, sheet_name)
        else:
            return self._load_excel(sheet_url)

    def _load_excel(self, sheet_url: str) -> pd.DataFrame:
        """Load data from Excel file."""
        df = pd.read_excel(sheet_url)

        # Validate required columns
        required_columns = ["Question", "Expected Answer"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Add missing optional columns
        columns = [
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
        for col in columns:
            if col not in df.columns:
                df[col] = ""

        return df

    def _load_google_sheets(self, sheet_url: str, sheet_name: str) -> pd.DataFrame:
        """Load data from Google Sheets."""
        if not GSHEETS_AVAILABLE:
            raise ImportError(
                "gspread library not available. Install with: pip install gspread oauth2client google-auth"
            )

        sheet_id, gid = self._extract_sheet_id_and_gid(sheet_url)

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
        if sheet_name:
            worksheet = spreadsheet.worksheet(sheet_name)
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
        columns = [
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
        for col in columns:
            if col not in df.columns:
                df[col] = ""

        return df

    def save_data(
        self,
        df: pd.DataFrame,
        sheet_url: str,
        sheet_name: str = "Automated",
        save_local: bool = False,
    ):
        """Save the updated DataFrame to Google Sheets, Excel, or local reports directory."""
        if save_local:
            self._save_local_reports(df)
        elif self._is_google_sheets_url(sheet_url):
            self._save_google_sheets(df, sheet_url, sheet_name)
        else:
            self._save_excel(df, sheet_url)

    def _save_excel(self, df: pd.DataFrame, sheet_url: str):
        """Save the updated DataFrame to Excel."""
        # Create backup before overwriting
        if os.path.exists(sheet_url):
            from datetime import datetime

            backup_path = (
                f"{sheet_url}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            os.rename(sheet_url, backup_path)
            self.logger.info(f"Created backup: {backup_path}")

        df.to_excel(sheet_url, index=False)
        self.logger.info(f"Saved results to: {sheet_url}")

    def _save_local_reports(self, df: pd.DataFrame):
        """Save data to local Excel file in reports directory with timestamp."""
        # Create reports directory if it doesn't exist
        reports_dir = Path(__file__).parent.parent.parent.parent / "reports"
        reports_dir.mkdir(exist_ok=True)

        # Generate timestamped filename
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"qa_results_{timestamp}.xlsx"
        filepath = reports_dir / filename

        # Save to Excel
        df.to_excel(filepath, index=False)
        self.logger.info(f"Saved results to local file: {filepath}")

    def _save_google_sheets(self, df: pd.DataFrame, sheet_url: str, sheet_name: str):
        """Save data to Google Sheets."""
        if not GSHEETS_AVAILABLE:
            raise ImportError(
                "gspread library not available. Install with: pip install gspread oauth2client google-auth"
            )

        sheet_id, gid = self._extract_sheet_id_and_gid(sheet_url)

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
        if sheet_name:
            worksheet = spreadsheet.worksheet(sheet_name)
        else:
            worksheet = spreadsheet.get_worksheet_by_id(int(gid))

        # Clear existing data and update with new data
        worksheet.clear()
        worksheet.update([df.columns.tolist()] + df.values.tolist())

        self.logger.info(f"Saved results to Google Sheets: {sheet_url}")

    async def fetch_customers(self, jwt_token: str) -> Dict[str, str]:
        """Fetch all customers from the API and return a mapping of customer names to IDs."""
        url = f"{self.api_base_url}/api/v1/customers"

        headers = {"Content-Type": "application/json"}
        if jwt_token:
            headers["Authorization"] = f"Bearer {jwt_token}"

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
            return {}

    async def call_chat_api(
        self, question: str, jwt_token: str, customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Call the chat API with a question."""
        url = f"{self.api_base_url}/api/v1/chat"

        headers = {"Content-Type": "application/json"}
        if jwt_token:
            headers["Authorization"] = f"Bearer {jwt_token}"

        payload = {
            "message": question,
            # Don't include thread_id to ensure fresh conversation each time
        }

        if customer_id:
            payload["customer_id"] = customer_id

        try:
            response = await self.client.post(
                url, json=json.dumps(payload), headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            self.logger.error(f"API Error: {str(e)}")
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
        """Use LLM to rank the answers and provide suggestions."""
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

        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=self.settings.gemini_api_key)  # type: ignore
            model = genai.GenerativeModel("gemini-2.5-flash")  # type: ignore

            response = model.generate_content(prompt)
            result_text = response.text.strip()

            # Try to parse JSON from the response
            # Handle markdown code blocks
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            import json

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
        jwt_token: str,
        customer_id: Optional[str] = None,
    ) -> tuple[int, str, str, str, str, str]:
        """Process a single test case."""
        row = df.loc[idx]
        question = row["Question"]
        expected_answer = row["Expected Answer"]
        previous_answer = row["Previous Answer"]

        self.logger.info(f"[{idx + 1}] Testing: {question[:60]}...")

        # Call chat API and capture start time
        start_time = datetime.now()
        self.logger.debug("  → Calling chat API...")
        response = await self.call_chat_api(question, jwt_token, customer_id)
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
        self.logger.debug("  → Ranking with LLM...")
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

    async def run_qa_test(
        self,
        sheet_url: str,
        jwt_token: str,
        customer_name: Optional[str] = None,
        start_row: int = 0,
        end_row: Optional[int] = None,
        sheet_name: str = "Automated",
        fail_fast: bool = True,
        max_concurrent: int = 5,
        fill_blanks: bool = False,
        save_local: bool = False,
    ) -> Dict[str, Any]:
        """Run the complete QA testing workflow."""
        self.logger.info("=" * 80)
        self.logger.info("QA Testing API")
        self.logger.info("=" * 80)

        # Convert customer_name to customer_id if provided
        customer_id = None
        if customer_name and customer_name.strip():
            self.logger.info(f"Converting customer name '{customer_name}' to ID...")
            customer_map = await self.fetch_customers(jwt_token)
            if customer_name in customer_map:
                customer_id = customer_map[customer_name]
                self.logger.info(f"Found customer ID: {customer_id}")
            else:
                self.logger.warning(
                    f"Customer name '{customer_name}' not found in available customers"
                )
                self.logger.info(f"Available customers: {list(customer_map.keys())}")

        # Load data
        source_type = (
            "Google Sheets" if self._is_google_sheets_url(sheet_url) else "Excel file"
        )
        self.logger.info(f"Loading {source_type}: {sheet_url}")
        df = self.load_data(sheet_url, sheet_name)
        self.logger.info(f"Loaded {len(df)} test cases")

        # Move current to previous (or fill blanks)
        if not fill_blanks:
            self.logger.info("Moving current answers to previous...")
            df["Previous Answer"] = df["Current Answer"]
            df["Current Answer"] = ""
        else:
            self.logger.info("Fill-blanks mode: preserving existing answers")

        self.save_data(df, sheet_url, sheet_name, save_local)

        # Process test cases
        end_row = end_row or len(df)
        rows_to_process = list(range(start_row, end_row))

        total_rows = len(rows_to_process)
        self.logger.info(f"Processing {total_rows} test cases...")

        # Process all rows in parallel with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        self.logger.info(
            f"Processing {total_rows} test cases in parallel (max {max_concurrent} concurrent)..."
        )

        async def process_with_semaphore(idx):
            async with semaphore:
                return await self.process_single_test_case(
                    df, idx, jwt_token, customer_id
                )

        tasks = [process_with_semaphore(idx) for idx in rows_to_process]
        results = await asyncio.gather(*tasks)

        # Update DataFrame with results
        for idx, current_answer, rank, suggestion, trace_link, log_link in results:
            df.at[idx, "Current Answer"] = current_answer
            df.at[idx, "Rank"] = rank
            df.at[idx, "Suggestion"] = suggestion
            df.at[idx, "Chat Trace Link"] = trace_link
            df.at[idx, "Log Link"] = log_link

        # Final save
        self.save_data(df, sheet_url, sheet_name, save_local)

        # Calculate ranking distribution
        rank_counts = df["Rank"].value_counts().to_dict()

        # Print summary
        self.logger.info("=" * 80)
        self.logger.info("SUMMARY")
        self.logger.info("=" * 80)

        self.logger.info("Ranking Distribution:")
        for rank, count in rank_counts.items():
            self.logger.info(f"  {rank}: {count}")

        save_location = "local reports directory" if save_local else sheet_url
        self.logger.info(f"Testing complete! Results saved to: {save_location}")
        self.logger.info("=" * 80)

        return {
            "total_rows": len(df),
            "processed_rows": total_rows,
            "ranking_distribution": rank_counts,
            "save_location": save_location,
        }
