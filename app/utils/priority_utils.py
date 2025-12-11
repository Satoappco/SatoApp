"""
Customer priority calculation utilities

Implements a weighted scoring system to prioritize customers based on:
- Business Impact: importance level and budget share
- Urgency: campaign health and recency of work
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any


@dataclass
class CustomerPriorityData:
    """Data class for customer priority calculation"""
    customer_id: int
    name: str
    importance: int        # 1-5 (5 is most important)
    budget: float          # Monthly budget in customer's currency
    campaign_health: int   # 1 (bad) to 5 (excellent)
    last_work_date: datetime | None  # Date of last work on customer


def compute_priority_score(
    customer: CustomerPriorityData,
    total_budget: float
) -> Dict[str, Any]:
    """
    Compute priority score (0-100) for a single customer.

    Formula components:
      I_norm        = importance / 5
      BudgetShare   = budget / total_budget
      C_urg_norm    = (6 - campaign_health) / 5
      R_norm        = min(days_since_last / 14, 1)

      BusinessImpact = 0.6 * I_norm + 0.4 * BudgetShare
      Urgency        = 0.8 * C_urg_norm + 0.2 * R_norm

      TotalRaw = 0.55 * BusinessImpact + 0.45 * Urgency
      Score    = round(100 * TotalRaw)

    Args:
        customer: CustomerPriorityData with all required fields
        total_budget: Total budget across all customers for proportional calculation

    Returns:
        Dictionary with score, components, and normalized values
    """
    if total_budget <= 0:
        raise ValueError("Total budget must be > 0 to compute proportional shares.")

    # Calculate days since last work
    if customer.last_work_date is None:
        days_since_last = 14  # Default to max urgency if never worked on
    else:
        days_since_last = (datetime.utcnow() - customer.last_work_date).days

    # Normalizations
    I_norm = customer.importance / 5.0
    budget_share = customer.budget / total_budget if total_budget > 0 else 0

    # Campaign urgency (1 = worst → 1.0 urgency, 5 = best → 0.2 urgency)
    C_urg_norm = (6 - customer.campaign_health) / 5.0

    # Recency (capped at 14 days)
    R_norm = min(days_since_last / 14.0, 1.0)

    # Components
    business_impact = 0.6 * I_norm + 0.4 * budget_share
    urgency = 0.8 * C_urg_norm + 0.2 * R_norm

    total_raw = 0.55 * business_impact + 0.45 * urgency
    score = round(100 * total_raw)

    return {
        "customer_id": customer.customer_id,
        "name": customer.name,
        "score": score,
        "business_impact": round(business_impact, 3),
        "urgency": round(urgency, 3),
        "components": {
            "I_norm": round(I_norm, 3),
            "budget_share": round(budget_share, 3),
            "C_urg_norm": round(C_urg_norm, 3),
            "R_norm": round(R_norm, 3),
            "days_since_last": days_since_last,
        }
    }


def compute_priority_scores(
    customers: List[CustomerPriorityData]
) -> List[Dict[str, Any]]:
    """
    Compute priority scores (0-100) for a list of customers.

    Args:
        customers: List of CustomerPriorityData objects

    Returns:
        List of dictionaries with scores and components, sorted by score descending

    Raises:
        ValueError: If total budget is <= 0
    """
    if not customers:
        return []

    total_budget = sum(c.budget for c in customers)
    if total_budget <= 0:
        raise ValueError("Total budget must be > 0 to compute proportional shares.")

    results = []
    for customer in customers:
        result = compute_priority_score(customer, total_budget)
        results.append(result)

    # Sort descending by score
    results.sort(key=lambda r: r["score"], reverse=True)
    return results
