"""
QA Testing Script for Chat API

This script processes an Excel table with predefined questions and evaluates chat responses.
Columns: question, expected_answer, current_answer, previous_answer, rank, suggestion

Process:
1. Move current_answer to previous_answer
2. Call chat route for each question (without reusing thread_id)
3. Save response in current_answer
4. Use LLM to rank: "both good", "previous better", "current better", "both bad"
5. Generate suggestions for improvement
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import pandas as pd
import httpx
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import get_settings

# Load environment variables
load_dotenv()


class QATestingScript:
    """QA Testing script for evaluating chat responses."""

    def __init__(
        self,
        excel_path: str,
        api_base_url: str = "http://localhost:8000",
        api_token: Optional[str] = None,
        llm_provider: str = "gemini"
    ):
        """
        Initialize the QA testing script.

        Args:
            excel_path: Path to the Excel file with test cases
            api_base_url: Base URL for the API
            api_token: JWT token for authentication
            llm_provider: LLM provider for ranking ("gemini" or "openai")
        """
        self.excel_path = excel_path
        self.api_base_url = api_base_url.rstrip("/")
        self.api_token = api_token
        self.llm_provider = llm_provider
        self.settings = get_settings()

        # Initialize HTTP client
        self.client = httpx.AsyncClient(timeout=120.0)

        # Column names
        self.columns = [
            "question",
            "expected_answer",
            "current_answer",
            "previous_answer",
            "rank",
            "suggestion"
        ]

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()

    def load_excel(self) -> pd.DataFrame:
        """Load the Excel file with test cases."""
        if not os.path.exists(self.excel_path):
            raise FileNotFoundError(f"Excel file not found: {self.excel_path}")

        df = pd.read_excel(self.excel_path)

        # Validate required columns
        required_columns = ["question", "expected_answer"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Add missing optional columns
        for col in self.columns:
            if col not in df.columns:
                df[col] = ""

        return df

    def save_excel(self, df: pd.DataFrame):
        """Save the updated DataFrame to Excel."""
        # Create backup before overwriting
        if os.path.exists(self.excel_path):
            backup_path = f"{self.excel_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(self.excel_path, backup_path)
            print(f"✅ Created backup: {backup_path}")

        df.to_excel(self.excel_path, index=False)
        print(f"✅ Saved results to: {self.excel_path}")

    def move_current_to_previous(self, df: pd.DataFrame) -> pd.DataFrame:
        """Move current_answer to previous_answer for all rows."""
        df["previous_answer"] = df["current_answer"]
        df["current_answer"] = ""
        print("✅ Moved current answers to previous")
        return df

    async def call_chat_api(self, question: str, customer_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Call the chat API with a question.

        Args:
            question: The question to ask
            customer_id: Optional customer ID

        Returns:
            Dictionary with response data
        """
        url = f"{self.api_base_url}/api/v1/chat"

        headers = {
            "Content-Type": "application/json"
        }

        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

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
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            return {"error": str(e), "message": ""}

    async def rank_with_llm(
        self,
        question: str,
        expected_answer: str,
        current_answer: str,
        previous_answer: str
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
            model = genai.GenerativeModel("gemini-1.5-flash")

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
                print(f"⚠️  Invalid rank: {result.get('rank')}, defaulting to 'both bad'")
                result["rank"] = "both bad"

            return result

        except Exception as e:
            print(f"❌ LLM Ranking Error: {str(e)}")
            return {
                "rank": "both bad",
                "suggestion": f"Error during ranking: {str(e)}"
            }

    async def process_test_cases(
        self,
        df: pd.DataFrame,
        start_row: int = 0,
        end_row: Optional[int] = None,
        customer_id: Optional[int] = None
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

        print(f"\n🚀 Processing {total_rows} test cases (rows {start_row} to {end_row-1})...\n")

        for idx in range(start_row, end_row):
            row = df.iloc[idx]
            question = row["question"]
            expected_answer = row["expected_answer"]
            previous_answer = row["previous_answer"]

            print(f"[{idx+1}/{end_row}] Testing: {question[:60]}...")

            # Call chat API
            print(f"  → Calling chat API...")
            response = await self.call_chat_api(question, customer_id)
            current_answer = response.get("message", "")

            if response.get("error"):
                current_answer = f"ERROR: {response['error']}"

            df.at[idx, "current_answer"] = current_answer
            print(f"  ✅ Got response: {current_answer[:100]}...")

            # Rank with LLM
            print(f"  → Ranking with LLM...")
            ranking = await self.rank_with_llm(
                question=question,
                expected_answer=expected_answer,
                current_answer=current_answer,
                previous_answer=previous_answer
            )

            df.at[idx, "rank"] = ranking.get("rank", "both bad")
            df.at[idx, "suggestion"] = ranking.get("suggestion", "")

            print(f"  ✅ Rank: {ranking.get('rank')}")
            print(f"  💡 Suggestion: {ranking.get('suggestion')[:80]}...")
            print()

            # Save progress after each row
            self.save_excel(df)

        return df

    async def run(
        self,
        start_row: int = 0,
        end_row: Optional[int] = None,
        customer_id: Optional[int] = None
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

        # Load Excel
        print(f"\n📂 Loading Excel file: {self.excel_path}")
        df = self.load_excel()
        print(f"✅ Loaded {len(df)} test cases")

        # Move current to previous
        print(f"\n🔄 Moving current answers to previous...")
        df = self.move_current_to_previous(df)
        self.save_excel(df)

        # Process test cases
        df = await self.process_test_cases(df, start_row, end_row, customer_id)

        # Final save
        self.save_excel(df)

        # Print summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        rank_counts = df["rank"].value_counts()
        print("\nRanking Distribution:")
        for rank, count in rank_counts.items():
            print(f"  {rank}: {count}")

        print(f"\n✅ Testing complete! Results saved to: {self.excel_path}")
        print("=" * 80)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="QA Testing Script for Chat API")
    parser.add_argument(
        "excel_path",
        help="Path to Excel file with test cases"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--api-token",
        help="JWT authentication token (can also use API_TOKEN env var)"
    )
    parser.add_argument(
        "--customer-id",
        type=int,
        help="Customer ID to use for all requests"
    )
    parser.add_argument(
        "--start-row",
        type=int,
        default=0,
        help="Starting row index (0-based, default: 0)"
    )
    parser.add_argument(
        "--end-row",
        type=int,
        help="Ending row index (exclusive, default: all rows)"
    )
    parser.add_argument(
        "--llm-provider",
        choices=["gemini"],
        default="gemini",
        help="LLM provider for ranking (default: gemini)"
    )

    args = parser.parse_args()

    # Get API token from args or environment
    api_token = args.api_token or os.getenv("API_TOKEN")

    if not api_token:
        print("⚠️  Warning: No API token provided. Set API_TOKEN env var or use --api-token")
        print("   Authentication may fail if the API requires it.")

    # Run the script
    async with QATestingScript(
        excel_path=args.excel_path,
        api_base_url=args.api_url,
        api_token=api_token,
        llm_provider=args.llm_provider
    ) as script:
        await script.run(
            start_row=args.start_row,
            end_row=args.end_row,
            customer_id=args.customer_id
        )


if __name__ == "__main__":
    asyncio.run(main())
