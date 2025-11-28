#!/usr/bin/env python3
"""
Crew Conversation Script

This script starts a conversation with the AnalyticsCrew for a given campaign and customer.
It prompts the user for input, sends it to the crew, and displays the response along with logging data.

If campaigner or customer IDs are not provided, it will interactively prompt the user to select them.

 Usage:
     python scripts/crew_conversation.py --campaign-id <id> --customer-id <id> [--prompt "message"]
     python scripts/crew_conversation.py  # Interactive selection

 Examples:
     python scripts/crew_conversation.py --campaign-id 123 --customer-id 456 --prompt "Analyze my campaign performance"
     python scripts/crew_conversation.py -c 123 -u 456 -m "Show me the latest metrics"
     python scripts/crew_conversation.py  # Interactive mode
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.agents.crew.crew import AnalyticsCrew
from app.config.database import get_session
from app.models.users import Campaigner, Customer, CustomerCampaignerAssignment
from sqlmodel import select
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_campaigners() -> List[Dict[str, Any]]:
    """Fetch all campaigners from the database."""
    try:
        with get_session() as session:
            campaigners = session.exec(
                select(Campaigner).where(Campaigner.status == "active")
            ).all()

            return [
                {
                    "id": c.id,
                    "full_name": c.full_name,
                    "email": c.email,
                    "agency_id": c.agency_id,
                }
                for c in campaigners
            ]
    except Exception as e:
        logger.error(f"Failed to fetch campaigners: {e}")
        return []


def get_customers_for_campaigner(campaigner_id: int) -> List[Dict[str, Any]]:
    """Fetch all customers assigned to a specific campaigner."""
    try:
        with get_session() as session:
            # Get customers through the assignment table
            assignments = session.exec(
                select(CustomerCampaignerAssignment).where(
                    CustomerCampaignerAssignment.campaigner_id == campaigner_id
                )
            ).all()

            customer_ids = [assignment.customer_id for assignment in assignments]

            if not customer_ids:
                return []

            # Fetch all active customers and filter by assigned customer_ids
            all_customers = session.exec(
                select(Customer).where(Customer.is_active == True)
            ).all()

            # Filter customers that are assigned to this campaigner
            assigned_customers = [c for c in all_customers if c.id in customer_ids]

            return [
                {
                    "id": c.id,
                    "full_name": c.full_name,
                    "contact_email": c.contact_email,
                    "status": c.status,
                }
                for c in assigned_customers
            ]
    except Exception as e:
        logger.error(f"Failed to fetch customers for campaigner {campaigner_id}: {e}")
        return []


def select_from_list(
    items: List[Dict[str, Any]], item_type: str, display_key: str = "full_name"
) -> Optional[Dict[str, Any]]:
    """Interactive selection from a list of items."""
    if not items:
        print(f"❌ No {item_type}s found.")
        return None

    print(f"\nAvailable {item_type}s:")
    print("-" * 50)

    for i, item in enumerate(items, 1):
        display_name = item.get(display_key, f"Item {i}")
        email = item.get("email", item.get("contact_email", ""))
        if email:
            print(f"{i}. {display_name} ({email})")
        else:
            print(f"{i}. {display_name}")

    print()

    while True:
        try:
            choice = (
                input(f"Select a {item_type} (1-{len(items)}) or 'q' to quit: ")
                .strip()
                .lower()
            )

            if choice == "q":
                return None

            choice_num = int(choice)
            if 1 <= choice_num <= len(items):
                return items[choice_num - 1]
            else:
                print(f"❌ Please enter a number between 1 and {len(items)}")

        except ValueError:
            print("❌ Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\n❌ Selection cancelled")
            return None


def get_campaigner_and_customer_interactive() -> Tuple[Optional[int], Optional[int]]:
    """Interactively select campaigner and customer."""
    print("🔍 Interactive Selection Mode")
    print("=" * 40)

    # Select campaigner
    campaigners = get_campaigners()
    selected_campaigner = select_from_list(campaigners, "campaigner")

    if not selected_campaigner:
        return None, None

    campaigner_id = selected_campaigner["id"]
    campaigner_name = selected_campaigner["full_name"]

    print(f"✅ Selected campaigner: {campaigner_name} [id:{campaigner_id}]")
    print()

    # Select customer
    customers = get_customers_for_campaigner(campaigner_id)
    selected_customer = select_from_list(customers, "customer")

    if not selected_customer:
        return campaigner_id, None

    customer_id = selected_customer["id"]
    customer_name = selected_customer["full_name"]

    print(f"✅ Selected customer: {customer_name} [id:{customer_id}]")
    print()

    return campaigner_id, customer_id


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Start a conversation with the AnalyticsCrew",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
 Examples:
   python scripts/crew_conversation.py --campaign-id 123 --customer-id 456 --prompt "Analyze my campaign performance"
   python scripts/crew_conversation.py -c 123 -u 456 -m "Show me the latest metrics"
   python scripts/crew_conversation.py  # Interactive selection
        """,
    )

    parser.add_argument(
        "--campaign-id",
        "-c",
        type=int,
        help="Campaign ID (campaigner_id) - if not provided, will prompt for selection",
    )

    parser.add_argument(
        "--customer-id",
        "-u",
        type=int,
        help="Customer ID - if not provided, will prompt for selection",
    )

    parser.add_argument(
        "--platforms",
        "-p",
        nargs="+",
        choices=["facebook", "facebook_ads", "google_analytics", "google_ads"],
        help="Specific platforms to use (optional, will auto-detect if not provided)",
    )

    parser.add_argument(
        "--thread-id", "-t", type=str, help="Thread ID for tracing (optional)"
    )

    parser.add_argument(
        "--level", "-l", type=int, default=1, help="Tracing level (default: 1)"
    )

    parser.add_argument(
        "--prompt",
        "-m",
        type=str,
        help="Initial prompt message (optional, will prompt if not provided)",
    )

    args = parser.parse_args()

    # Handle campaigner and customer selection
    campaigner_id = args.campaign_id
    customer_id = args.customer_id

    # If campaigner not provided, or if customer not provided and we need to select campaigner first
    if campaigner_id is None or (customer_id is None and campaigner_id is None):
        selected_campaigner_id, selected_customer_id = (
            get_campaigner_and_customer_interactive()
        )

        if selected_campaigner_id is None:
            print("❌ No campaigner selected. Exiting.")
            return 1

        campaigner_id = selected_campaigner_id

        if selected_customer_id is None:
            print("❌ No customer selected. Exiting.")
            return 1

        customer_id = selected_customer_id
    elif customer_id is None:
        # Campaigner provided but customer not - select customer for this campaigner
        customers = get_customers_for_campaigner(campaigner_id)
        selected_customer = select_from_list(customers, "customer")

        if not selected_customer:
            print("❌ No customer selected. Exiting.")
            return 1

        customer_id = selected_customer["id"]
        customer_name = selected_customer["full_name"]
        print(f"✅ Selected customer: {customer_name}")
        print()

    print("=" * 80)
    print("AnalyticsCrew Conversation")
    print("=" * 80)
    print(f"Campaigner ID: {campaigner_id}")
    print(f"Customer ID: {customer_id}")
    if args.platforms:
        print(f"Platforms: {', '.join(args.platforms)}")
    print()

    # Get user input - either from args or prompt
    if args.prompt:
        user_query = args.prompt.strip()
    else:
        user_query = input("Enter your message for the crew: ").strip()

    if not user_query:
        print("❌ No input provided. Exiting.")
        return 1

    print()
    print("=" * 80)
    print("Processing your request...")
    print("=" * 80)
    print(f"Query: {user_query[:200]}{'...' if len(user_query) > 200 else ''}")
    print()

    try:
        # Initialize the crew
        logger.info(
            f"Initializing AnalyticsCrew for campaign {args.campaign_id}, customer {args.customer_id}"
        )
        crew = AnalyticsCrew()

        # Prepare task details
        task_details = {
            "campaigner_id": campaigner_id,
            "customer_id": customer_id,
            "query": user_query,
        }

        if args.platforms:
            task_details["platforms"] = args.platforms

        if args.thread_id:
            task_details["thread_id"] = args.thread_id

        task_details["level"] = args.level

        logger.info(f"Starting crew execution with task details: {task_details}")

        # Execute the crew
        result = crew.execute(task_details)

        print("=" * 80)
        print("CREW RESPONSE")
        print("=" * 80)

        if result.get("success"):
            print("✅ Crew execution successful!")
            print()

            # Print the main result
            crew_result = result.get("result")
            if crew_result:
                if hasattr(crew_result, "raw"):
                    response_text = str(crew_result.raw)
                else:
                    response_text = str(crew_result)

                print("RESPONSE:")
                print("-" * 40)
                print(response_text)
                print()
            else:
                print("⚠️  No result returned from crew")
                print()

            # Print logging data
            print("LOGGING DATA:")
            print("-" * 40)
            logging_info = {
                "platforms": result.get("platforms", []),
                "task_details": result.get("task_details", {}),
                "session_id": result.get("session_id"),
                "success": result.get("success"),
            }
            print(json.dumps(logging_info, indent=2, default=str))

        else:
            print("❌ Crew execution failed!")
            print(f"Error: {result.get('error', 'Unknown error')}")
            print()

            # Print logging data for failed execution
            print("LOGGING DATA:")
            print("-" * 40)
            logging_info = {
                "platforms": result.get("platforms", []),
                "task_details": result.get("task_details", {}),
                "session_id": result.get("session_id"),
                "success": result.get("success"),
                "error": result.get("error"),
            }
            print(json.dumps(logging_info, indent=2, default=str))

        print("=" * 80)
        return 0

    except Exception as e:
        logger.error(f"❌ Script execution failed: {e}", exc_info=True)
        print(f"❌ Script execution failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
