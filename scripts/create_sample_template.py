"""
Create a sample Excel template for QA testing.

Run this script to generate a sample qa_test_cases.xlsx file with example test cases.
"""

import pandas as pd
from pathlib import Path

def create_sample_template():
    """Create a sample Excel template with test cases."""

    # Sample test cases
    data = {
        "question": [
            "Show me Facebook Ads performance for last month",
            "What were my Google Ads impressions yesterday?",
            "Compare Facebook and Google Ads spend for this week",
            "Show me top performing campaigns",
            "What's my ROAS for the last quarter?",
        ],
        "expected_answer": [
            "A response that clarifies which metrics the user wants to see (clicks, impressions, spend, etc.) and confirms the date range (last month).",
            "A response that asks for clarification on which account/property to use or provides the impressions data if already connected.",
            "A response that asks for specific metrics to compare and confirms the date range (this week).",
            "A response that asks which platform (Facebook, Google, or both) and what metric defines 'top performing' (ROAS, CTR, conversions, etc.).",
            "A response that asks which platform(s) and may ask for clarification on how ROAS is calculated if not standard.",
        ],
        "current_answer": [
            "",
            "",
            "",
            "",
            "",
        ],
        "previous_answer": [
            "",
            "",
            "",
            "",
            "",
        ],
        "rank": [
            "",
            "",
            "",
            "",
            "",
        ],
        "suggestion": [
            "",
            "",
            "",
            "",
            "",
        ],
    }

    df = pd.DataFrame(data)

    # Save to Excel
    output_path = Path(__file__).parent / "qa_test_cases.xlsx"
    df.to_excel(output_path, index=False)

    print(f"✅ Created sample template: {output_path}")
    print(f"📋 Contains {len(df)} sample test cases")
    print("\nYou can now run the QA testing script with:")
    print(f"   python tests/qa_testing_script.py {output_path}")

if __name__ == "__main__":
    create_sample_template()
