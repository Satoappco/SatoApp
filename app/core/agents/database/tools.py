"""Database query tools for agents (read-only access)."""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import text

from .connection import get_db_connection

logger = logging.getLogger(__name__)


class DatabaseTool:
    """Base class for database query tools."""

    def __init__(self, campaigner_id: int):
        """
        Initialize database tool.

        Args:
            campaigner_id: ID of the authenticated campaigner (for authorization)
        """
        self.campaigner_id = campaigner_id
        logger.debug(f"🔧 [DatabaseTool] Initialized for campaigner_id: {campaigner_id}")

    def _execute_query(self, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute a read-only query and return results.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of result dictionaries
        """
        logger.debug(f"🔍 [DatabaseTool] Executing query with params: {params}")

        try:
            with get_db_connection() as session:
                result = session.execute(text(query), params)
                rows = result.fetchall()

                # Convert to list of dicts
                results = []
                if rows:
                    columns = result.keys()
                    results = [dict(zip(columns, row)) for row in rows]

                logger.info(f"✅ [DatabaseTool] Query returned {len(results)} rows")
                return results

        except Exception as e:
            logger.error(f"❌ [DatabaseTool] Query failed: {str(e)}", exc_info=True)
            raise

    def get_agency_info(self) -> Optional[Dict[str, Any]]:
        """
        Get agency information for the current campaigner.

        Returns:
            Agency information or None if not found
        """
        query = """
        SELECT a.id, a.name, a.email, a.phone, a.status, a.created_at
        FROM agencies a
        JOIN campaigners c ON c.agency_id = a.id
        WHERE c.id = :campaigner_id
        """

        logger.info(f"🏢 [DatabaseTool] Getting agency info for campaigner: {self.campaigner_id}")
        results = self._execute_query(query, {"campaigner_id": self.campaigner_id})

        return results[0] if results else None

    def get_campaigner_info(self) -> Optional[Dict[str, Any]]:
        """
        Get campaigner information.

        Returns:
            Campaigner information or None if not found
        """
        query = """
        SELECT id, email, full_name, phone, role, status, locale, timezone, agency_id
        FROM campaigners
        WHERE id = :campaigner_id
        """

        logger.info(f"👤 [DatabaseTool] Getting campaigner info: {self.campaigner_id}")
        results = self._execute_query(query, {"campaigner_id": self.campaigner_id})

        return results[0] if results else None

    def get_customers_for_campaigner(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all customers for the campaigner's agency.

        Args:
            limit: Maximum number of results (default: 100)

        Returns:
            List of customer records
        """
        query = """
        SELECT c.id, c.full_name, c.status, c.contact_email, c.phone,
               c.website_url, c.facebook_page_url, c.instagram_page_url,
               c.assigned_campaigner_id, c.is_active, c.created_at
        FROM customers c
        JOIN campaigners camp ON camp.agency_id = c.agency_id
        WHERE camp.id = :campaigner_id
          AND c.is_active = true
        ORDER BY c.created_at DESC
        LIMIT :limit
        """

        logger.info(f"👥 [DatabaseTool] Getting customers for campaigner: {self.campaigner_id}")
        return self._execute_query(query, {"campaigner_id": self.campaigner_id, "limit": limit})

    def get_customer_info(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed customer information.

        Args:
            customer_id: Customer ID

        Returns:
            Customer information or None if not found/not authorized
        """
        query = """
        SELECT c.id, c.full_name, c.status, c.contact_email, c.phone, c.address,
               c.opening_hours, c.website_url, c.facebook_page_url, c.instagram_page_url,
               c.assigned_campaigner_id, c.is_active, c.created_at, c.updated_at,
               c.llm_engine_preference
        FROM customers c
        JOIN campaigners camp ON camp.agency_id = c.agency_id
        WHERE c.id = :customer_id
          AND camp.id = :campaigner_id
          AND c.is_active = true
        """

        logger.info(
            f"🏪 [DatabaseTool] Getting customer info: {customer_id} "
            f"for campaigner: {self.campaigner_id}"
        )
        results = self._execute_query(
            query, {"customer_id": customer_id, "campaigner_id": self.campaigner_id}
        )

        return results[0] if results else None

    def get_kpi_goals(
        self, customer_id: int, limit: int = 50, campaign_status: str = "ACTIVE"
    ) -> List[Dict[str, Any]]:
        """
        Get KPI goals for a specific customer.

        Args:
            customer_id: Customer ID
            limit: Maximum number of results (default: 50)
            campaign_status: Filter by campaign status (default: "ACTIVE")

        Returns:
            List of KPI goal records
        """
        query = """
        SELECT kg.id, kg.campaign_id, kg.campaign_name, kg.campaign_status,
               kg.ad_group_id, kg.ad_group_name, kg.ad_id, kg.ad_name,
               kg.advertising_channel, kg.campaign_objective, kg.daily_budget,
               kg.target_audience, kg.primary_kpi_1, kg.secondary_kpi_1,
               kg.secondary_kpi_2, kg.secondary_kpi_3, kg.landing_page,
               kg.created_at, kg.updated_at
        FROM kpi_goals kg
        JOIN customers c ON c.id = kg.customer_id
        JOIN campaigners camp ON camp.agency_id = c.agency_id
        WHERE kg.customer_id = :customer_id
          AND camp.id = :campaigner_id
          AND kg.campaign_status = :campaign_status
        ORDER BY kg.updated_at DESC
        LIMIT :limit
        """

        logger.info(
            f"🎯 [DatabaseTool] Getting KPI goals for customer: {customer_id}, "
            f"status: {campaign_status}"
        )
        return self._execute_query(
            query,
            {
                "customer_id": customer_id,
                "campaigner_id": self.campaigner_id,
                "campaign_status": campaign_status,
                "limit": limit,
            },
        )

    def get_campaigns_summary(self, customer_id: int) -> Dict[str, Any]:
        """
        Get summary statistics of campaigns for a customer.

        Args:
            customer_id: Customer ID

        Returns:
            Dictionary with campaign statistics
        """
        query = """
        SELECT
            COUNT(DISTINCT campaign_id) as total_campaigns,
            COUNT(DISTINCT CASE WHEN campaign_status = 'ACTIVE' THEN campaign_id END) as active_campaigns,
            COUNT(DISTINCT CASE WHEN campaign_status = 'PAUSED' THEN campaign_id END) as paused_campaigns,
            COUNT(DISTINCT ad_group_id) as total_ad_groups,
            COUNT(DISTINCT ad_id) as total_ads,
            AVG(daily_budget) as avg_daily_budget,
            SUM(daily_budget) as total_daily_budget
        FROM kpi_goals kg
        JOIN customers c ON c.id = kg.customer_id
        JOIN campaigners camp ON camp.agency_id = c.agency_id
        WHERE kg.customer_id = :customer_id
          AND camp.id = :campaigner_id
        """

        logger.info(f"📊 [DatabaseTool] Getting campaign summary for customer: {customer_id}")
        results = self._execute_query(
            query, {"customer_id": customer_id, "campaigner_id": self.campaigner_id}
        )

        return results[0] if results else {}

    def search_campaigns(
        self, customer_id: int, search_term: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search campaigns by name or objective.

        Args:
            customer_id: Customer ID
            search_term: Search term for campaign name or objective
            limit: Maximum number of results (default: 20)

        Returns:
            List of matching campaign records
        """
        query = """
        SELECT DISTINCT ON (kg.campaign_id)
            kg.campaign_id, kg.campaign_name, kg.campaign_status,
            kg.advertising_channel, kg.campaign_objective, kg.daily_budget,
            kg.created_at
        FROM kpi_goals kg
        JOIN customers c ON c.id = kg.customer_id
        JOIN campaigners camp ON camp.agency_id = c.agency_id
        WHERE kg.customer_id = :customer_id
          AND camp.id = :campaigner_id
          AND (
              LOWER(kg.campaign_name) LIKE LOWER(:search_term)
              OR LOWER(kg.campaign_objective) LIKE LOWER(:search_term)
          )
        ORDER BY kg.campaign_id, kg.updated_at DESC
        LIMIT :limit
        """

        search_pattern = f"%{search_term}%"
        logger.info(
            f"🔎 [DatabaseTool] Searching campaigns for customer: {customer_id}, "
            f"term: '{search_term}'"
        )

        return self._execute_query(
            query,
            {
                "customer_id": customer_id,
                "campaigner_id": self.campaigner_id,
                "search_term": search_pattern,
                "limit": limit,
            },
        )

    def get_all_campaigns_for_campaigner(
        self, limit: int = 50, campaign_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all campaigns across all customers for the campaigner's agency.

        Args:
            limit: Maximum number of results (default: 50)
            campaign_status: Filter by campaign status (optional, e.g., "ACTIVE")

        Returns:
            List of campaign records with customer information
        """
        status_filter = ""
        params = {"campaigner_id": self.campaigner_id, "limit": limit}

        if campaign_status:
            status_filter = "AND kg.campaign_status = :campaign_status"
            params["campaign_status"] = campaign_status

        query = f"""
        SELECT DISTINCT ON (kg.campaign_id, c.id)
            kg.campaign_id, kg.campaign_name, kg.campaign_status,
            kg.advertising_channel, kg.campaign_objective, kg.daily_budget,
            kg.target_audience, kg.created_at, kg.updated_at,
            c.id as customer_id, c.full_name as customer_name
        FROM kpi_goals kg
        JOIN customers c ON c.id = kg.customer_id
        JOIN campaigners camp ON camp.agency_id = c.agency_id
        WHERE camp.id = :campaigner_id
          AND c.is_active = true
          {status_filter}
        ORDER BY kg.campaign_id, c.id, kg.updated_at DESC
        LIMIT :limit
        """

        logger.info(
            f"📋 [DatabaseTool] Getting all campaigns for campaigner: {self.campaigner_id}, "
            f"status: {campaign_status or 'all'}"
        )
        return self._execute_query(query, params)

    def get_campaigns_summary_all(self) -> Dict[str, Any]:
        """
        Get summary statistics of all campaigns for the campaigner's agency.

        Returns:
            Dictionary with campaign statistics across all customers
        """
        query = """
        SELECT
            COUNT(DISTINCT kg.campaign_id) as total_campaigns,
            COUNT(DISTINCT CASE WHEN kg.campaign_status = 'ACTIVE' THEN kg.campaign_id END) as active_campaigns,
            COUNT(DISTINCT CASE WHEN kg.campaign_status = 'PAUSED' THEN kg.campaign_id END) as paused_campaigns,
            COUNT(DISTINCT c.id) as total_customers,
            COUNT(DISTINCT kg.ad_group_id) as total_ad_groups,
            COUNT(DISTINCT kg.ad_id) as total_ads,
            AVG(kg.daily_budget) as avg_daily_budget,
            SUM(kg.daily_budget) as total_daily_budget
        FROM kpi_goals kg
        JOIN customers c ON c.id = kg.customer_id
        JOIN campaigners camp ON camp.agency_id = c.agency_id
        WHERE camp.id = :campaigner_id
          AND c.is_active = true
        """

        logger.info(f"📊 [DatabaseTool] Getting overall campaign summary for campaigner: {self.campaigner_id}")
        results = self._execute_query(query, {"campaigner_id": self.campaigner_id})

        return results[0] if results else {}

    def get_comprehensive_campaigner_info(self, customer_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get comprehensive campaigner information including agency, customers, digital assets, and connections.

        Args:
            customer_id: Optional customer ID to filter for specific customer

        Returns:
            Dictionary containing:
            - campaigner: User profile information
            - agency: Agency information
            - customers: List of customers with their digital assets and connections
        """
        # Base query for campaigner and agency
        base_query = """
        SELECT
            c.id as campaigner_id,
            c.full_name as campaigner_name,
            c.email as campaigner_email,
            c.role as campaigner_role,
            a.id as agency_id,
            a.name as agency_name
        FROM campaigners c
        JOIN agencies a ON c.agency_id = a.id
        WHERE c.id = :campaigner_id
        """

        logger.info(f"📋 [DatabaseTool] Getting comprehensive info for campaigner: {self.campaigner_id}")
        base_results = self._execute_query(base_query, {"campaigner_id": self.campaigner_id})

        if not base_results:
            return {}

        base_info = base_results[0]

        # Query for customers with digital assets and connections
        customer_filter = ""
        params = {"campaigner_id": self.campaigner_id}

        if customer_id:
            customer_filter = "AND cu.id = :customer_id"
            params["customer_id"] = customer_id

        customers_query = f"""
        SELECT
            cu.id as customer_id,
            cu.full_name as customer_name,
            cu.status as customer_type,
            cu.is_active as customer_plan,
            da.id as asset_id,
            da.asset_type as asset_type,
            da.provider as asset_provider,
            da.external_id as asset_external_id,
            da.status as asset_status,
            conn.id as connection_id,
            conn.account_email as connection_email,
            conn.expires_at as connection_expiration
        FROM campaigners c
        JOIN agencies a ON c.agency_id = a.id
        LEFT JOIN customers cu ON a.id = cu.agency_id
        LEFT JOIN digital_assets da ON cu.id = da.customer_id
        LEFT JOIN connections conn ON da.id = conn.digital_asset_id
        WHERE c.id = :campaigner_id {customer_filter}
        ORDER BY cu.id, da.id, conn.id
        """

        customer_results = self._execute_query(customers_query, params)

        # Organize data by customer
        customers_dict = {}
        for row in customer_results:
            cust_id = row.get('customer_id')
            if not cust_id:
                continue

            if cust_id not in customers_dict:
                customers_dict[cust_id] = {
                    'id': cust_id,
                    'name': row.get('customer_name'),
                    'type': row.get('customer_type'),
                    'plan': 'Active' if row.get('customer_plan') else 'Inactive',
                    'digital_assets': []
                }

            # Add digital asset if exists and not already added
            asset_id = row.get('asset_id')
            if asset_id:
                # Check if this asset is already in the list
                existing_asset = next(
                    (a for a in customers_dict[cust_id]['digital_assets'] if a['id'] == asset_id),
                    None
                )

                if not existing_asset:
                    asset = {
                        'id': asset_id,
                        'type': row.get('asset_type'),
                        'provider': row.get('asset_provider'),
                        'external_id': row.get('asset_external_id'),
                        'status': row.get('asset_status'),
                        'connections': []
                    }
                    customers_dict[cust_id]['digital_assets'].append(asset)
                else:
                    asset = existing_asset

                # Add connection if exists
                conn_id = row.get('connection_id')
                if conn_id and not any(c['id'] == conn_id for c in asset['connections']):
                    asset['connections'].append({
                        'id': conn_id,
                        'email': row.get('connection_email'),
                        'expiration': row.get('connection_expiration')
                    })

        return {
            'campaigner': {
                'id': base_info['campaigner_id'],
                'name': base_info['campaigner_name'],
                'email': base_info['campaigner_email'],
                'role': base_info['campaigner_role']
            },
            'agency': {
                'id': base_info['agency_id'],
                'name': base_info['agency_name']
            },
            'customers': list(customers_dict.values())
        }


# Convenience functions for backward compatibility
def get_agency_info(campaigner_id: int) -> Optional[Dict[str, Any]]:
    """Get agency info for a campaigner."""
    tool = DatabaseTool(campaigner_id)
    return tool.get_agency_info()


def get_campaigner_info(campaigner_id: int) -> Optional[Dict[str, Any]]:
    """Get campaigner info."""
    tool = DatabaseTool(campaigner_id)
    return tool.get_campaigner_info()


def get_customer_info(campaigner_id: int, customer_id: int) -> Optional[Dict[str, Any]]:
    """Get customer info."""
    tool = DatabaseTool(campaigner_id)
    return tool.get_customer_info(customer_id)


def get_kpi_goals(
    campaigner_id: int, customer_id: int, limit: int = 50, campaign_status: str = "ACTIVE"
) -> List[Dict[str, Any]]:
    """Get KPI goals for a customer."""
    tool = DatabaseTool(campaigner_id)
    return tool.get_kpi_goals(customer_id, limit, campaign_status)
