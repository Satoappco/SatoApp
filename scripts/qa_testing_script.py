"""
QA Testing Script for Chat API

This script processes a Google Sheets or Excel table with predefined questions and evaluates chat responses.
Columns: type, question, expected_answer, current_answer, previous_answer, rank, suggestion

Process:
1. Move current_answer to previous_answer
2. Call chat route for each question using JWT authentication (without reusing thread_id)
3. Save response in current_answer
4. Use LLM to rank: "both good", "previous better", "current better", "both bad"
5. Generate suggestions for improvement

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
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import pandas as pd
import httpx
from dotenv import load_dotenv

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

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
    ):
        """
        Initialize the QA testing script.

        Args:
            sheet_url: Google Sheets URL or path to Excel file with test cases
            api_base_url: Base URL for the API
            jwt_token: JWT token for authentication
            llm_provider: LLM provider for ranking ("gemini" or "openai")
            fail_fast: If True, stop processing a group when one question fails
        """
        self.sheet_url = sheet_url
        self.is_google_sheets = self._is_google_sheets_url(sheet_url)
        self.api_base_url = api_base_url.rstrip("/")
        self.jwt_token = jwt_token
        self.llm_provider = llm_provider
        self.fail_fast = fail_fast
        self.settings = get_settings()

        # Initialize HTTP client
        self.client = httpx.AsyncClient(timeout=120.0)

        # Column names
        self.columns = [
            "Type",
            "Question",
            "Expected Answer",
            "Current Answer",
            "Previous Answer",
            "Rank",
            "Suggestion",
        ]

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

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()

    def load_data(self) -> pd.DataFrame:
        """Load the test cases from Google Sheets or Excel file."""
        if self.is_google_sheets:
            return self._load_google_sheets()
        else:
            return self._load_excel()

    def _load_excel(self) -> pd.DataFrame:
        """Load the Excel file with test cases."""
        if not os.path.exists(self.sheet_url):
            raise FileNotFoundError(f"Excel file not found: {self.sheet_url}")

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

    def _load_google_sheets(self) -> pd.DataFrame:
        """Load data from Google Sheets."""
        if not GSHEETS_AVAILABLE:
            raise ImportError(
                "gspread library not available. Install with: pip install gspread oauth2client"
            )

        sheet_id, gid = self._extract_sheet_id_and_gid(self.sheet_url)

        # Authenticate with service account
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds_path = self.settings.google_sheets_service_account_path
        if not creds_path:
            raise ValueError(
                "Google Sheets service account path not configured in settings"
            )

        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        client = gspread.authorize(creds)

        # Open the spreadsheet and worksheet
        spreadsheet = client.open_by_key(sheet_id)
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
        """Save the updated DataFrame to Google Sheets or Excel."""
        if self.is_google_sheets:
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
            print(f"✅ Created backup: {backup_path}")

        df.to_excel(self.sheet_url, index=False)
        print(f"✅ Saved results to: {self.sheet_url}")

    def _save_google_sheets(self, df: pd.DataFrame):
        """Save data to Google Sheets."""
        if not GSHEETS_AVAILABLE:
            raise ImportError(
                "gspread library not available. Install with: pip install gspread oauth2client"
            )

        sheet_id, gid = self._extract_sheet_id_and_gid(self.sheet_url)

        # Authenticate with service account
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds_path = self.settings.google_sheets_service_account_path
        if not creds_path:
            raise ValueError(
                "Google Sheets service account path not configured in settings"
            )

        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        client = gspread.authorize(creds)

        # Open the spreadsheet and worksheet
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.get_worksheet_by_id(int(gid))

        # Clear existing data and update with new data
        worksheet.clear()
        worksheet.update([df.columns.tolist()] + df.values.tolist())

        print(f"✅ Saved results to Google Sheets: {self.sheet_url}")

    def move_current_to_previous(self, df: pd.DataFrame) -> pd.DataFrame:
        """Move current_answer to previous_answer for all rows."""
        df["Previous Answer"] = df["Current Answer"]
        df["Current Answer"] = ""
        print("✅ Moved current answers to previous")
        return df

    async def call_chat_api(
        self, question: str, customer_id: Optional[int] = None
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

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"❌ API Error: {str(e)}")
            if hasattr(e, "response") and e.response:
                print(f"Response: {e.response.text}")
            return {"error": str(e), "message": ""}

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
                print(
                    f"⚠️  Invalid rank: {result.get('rank')}, defaulting to 'both bad'"
                )
                result["rank"] = "both bad"

            return result

        except Exception as e:
            print(f"❌ LLM Ranking Error: {str(e)}")
            return {"rank": "both bad", "suggestion": f"Error during ranking: {str(e)}"}

    async def process_test_cases(
        self,
        df: pd.DataFrame,
        start_row: int = 0,
        end_row: Optional[int] = None,
        customer_id: Optional[int] = None,
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

        print(
            f"\n🚀 Processing {total_rows} test cases (rows {start_row} to {end_row - 1})...\n"
        )

        # Group by Type if fail_fast is enabled
        if self.fail_fast and "Type" in df.columns:
            # Process by groups
            grouped = df.iloc[start_row:end_row].groupby("Type", sort=False)
            for group_name, group_df in grouped:
                print(f"📁 Processing group: {group_name}")
                group_failed = False

                for idx in group_df.index:
                    if group_failed:
                        print(
                            f"  ⏭️  Skipping remaining questions in group '{group_name}' due to previous failure"
                        )
                        break

                    row = df.loc[idx]
                    question = row["Question"]
                    expected_answer = row["Expected Answer"]
                    previous_answer = row["Previous Answer"]

                    print(f"[{idx + 1}/{end_row}] Testing: {question[:60]}...")

                    # Call chat API
                    print(f"  → Calling chat API...")
                    response = await self.call_chat_api(question, customer_id)
                    current_answer = response.get("message", "")

                    if response.get("error"):
                        current_answer = f"ERROR: {response['error']}"

                    df.at[idx, "Current Answer"] = current_answer
                    print(f"  ✅ Got response: {current_answer[:100]}...")

                    # Rank with LLM
                    print(f"  → Ranking with LLM...")
                    ranking = await self.rank_with_llm(
                        question=question,
                        expected_answer=expected_answer,
                        current_answer=current_answer,
                        previous_answer=previous_answer,
                    )

                    rank = ranking.get("rank", "both bad")
                    df.at[idx, "Rank"] = rank
                    df.at[idx, "Suggestion"] = ranking.get("suggestion", "")

                    print(f"  ✅ Rank: {rank}")
                    print(f"  💡 Suggestion: {ranking.get('suggestion')[:80]}...")

                    # Check if this question failed and fail_fast is enabled
                    if self.fail_fast and rank == "both bad":
                        group_failed = True
                        print(
                            f"  ❌ Question failed with rank '{rank}', skipping remaining questions in group '{group_name}'"
                        )
                    print()
        else:
            # Process all rows individually (original behavior)
            for idx in range(start_row, end_row):
                row = df.iloc[idx]
                question = row["Question"]
                expected_answer = row["Expected Answer"]
                previous_answer = row["Previous Answer"]

                print(f"[{idx + 1}/{end_row}] Testing: {question[:60]}...")

                # Call chat API
                print(f"  → Calling chat API...")
                response = await self.call_chat_api(question, customer_id)
                current_answer = response.get("message", "")

                if response.get("error"):
                    current_answer = f"ERROR: {response['error']}"

                df.at[idx, "Current Answer"] = current_answer
                print(f"  ✅ Got response: {current_answer[:100]}...")

                # Rank with LLM
                print(f"  → Ranking with LLM...")
                ranking = await self.rank_with_llm(
                    question=question,
                    expected_answer=expected_answer,
                    current_answer=current_answer,
                    previous_answer=previous_answer,
                )

                df.at[idx, "Rank"] = ranking.get("rank", "both bad")
                df.at[idx, "Suggestion"] = ranking.get("suggestion", "")

                print(f"  ✅ Rank: {ranking.get('rank')}")
                print(f"  💡 Suggestion: {ranking.get('suggestion')[:80]}...")
                print()

        # Save progress after processing
        self.save_data(df)

        return df

    async def run(
        self,
        start_row: int = 0,
        end_row: Optional[int] = None,
        customer_id: Optional[int] = None,
    ):
        """
        Run the complete QA testing workflow.

        Args:
            start_row: Starting row index (0-based)
            end_row: Ending row index (exclusive), None for all rows
            customer_id: Optional customer ID to use for all requests
        """
        print("=" * 80)
        print("QA Testing Script for Chat API")
        print("=" * 80)

        # Load data
        source_type = "Google Sheets" if self.is_google_sheets else "Excel file"
        print(f"\n📂 Loading {source_type}: {self.sheet_url}")
        df = self.load_data()
        print(f"✅ Loaded {len(df)} test cases")

        # Move current to previous
        print(f"\n🔄 Moving current answers to previous...")
        df = self.move_current_to_previous(df)
        self.save_data(df)

        # Process test cases
        df = await self.process_test_cases(df, start_row, end_row, customer_id)

        # Final save
        self.save_data(df)

        # Print summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        rank_counts = df["Rank"].value_counts()
        print("\nRanking Distribution:")
        for rank, count in rank_counts.items():
            print(f"  {rank}: {count}")

        print(f"\n✅ Testing complete! Results saved to: {self.sheet_url}")
        print("=" * 80)


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
        "--customer-id", type=int, help="Customer ID to use for all requests"
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

    args = parser.parse_args()

    # Get JWT token from args or environment
    jwt_token = args.jwt_token or os.getenv("JWT_TOKEN")

    if not jwt_token:
        print("🔄 No JWT token provided, generating one for testing...")
        try:
            # Import here to avoid circular imports
            from app.core.auth import create_access_token

            jwt_token = create_access_token(
                data={"sub": "dor.yashar@gmail.com", "user_id": 10}
            )
            print(f"✅ Generated JWT token: {jwt_token[:5]}...{jwt_token[-5:]}")
        except Exception as e:
            print(f"❌ Failed to generate JWT token: {e}")
            print("   Set JWT_TOKEN env var or use --jwt-token")
            print(
                "   You can generate one manually with: python scripts/generate_test_token.py"
            )
            return
    else:
        print(f"🔑 Using JWT token: {jwt_token[:5]}...{jwt_token[-5:]}")

    # Run the script
    async with QATestingScript(
        sheet_url=args.sheet_url,
        api_base_url=args.api_url,
        jwt_token=jwt_token,
        llm_provider=args.llm_provider,
        fail_fast=args.fail_fast,
    ) as script:
        await script.run(
            start_row=args.start_row, end_row=args.end_row, customer_id=args.customer_id
        )


if __name__ == "__main__":
    asyncio.run(main())
