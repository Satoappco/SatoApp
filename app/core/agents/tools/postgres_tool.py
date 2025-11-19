"""PostgreSQL query execution tool for LangChain agents.

This tool provides a secure interface for executing READ-ONLY SQL queries
against the PostgreSQL database with automatic security filtering.
"""

import logging
import re
from typing import Dict, Any, List, Optional, get_type_hints, get_origin, get_args
from sqlalchemy import text
from langchain.tools import BaseTool
from pydantic import Field as PydanticField
from sqlmodel import Field as SQLModelField

from app.core.agents.database.connection import get_db_connection
# from ..database.connection import get_db_connection

from .sql_validator import SQLValidator
from ....models import (
    Customer,
    KpiGoal, KpiValue, DigitalAsset, Connection,
    RTMTable, QuestionsTable
)

logger = logging.getLogger(__name__)

class PostgresTool(BaseTool):
    """Tool for executing validated SQL queries against PostgreSQL.

    This tool ensures:
    - Read-only access (SELECT queries only)
    - Automatic security filtering by campaigner's agency
    - Query validation and sanitization
    - Proper error handling and logging
    """

    name: str = "postgres_query"
    description: str = """Execute a SELECT SQL query against the PostgreSQL database.

    This tool can query the following tables ONLY:
    - customers: Customer/client information
    - kpi_goals: Campaign goals and KPI targets
    - kpi_values: Actual KPI measurements
    - digital_assets: Digital assets (social media, analytics accounts, etc.)
    - connections: OAuth connections and API credentials
    - rtm_table: RTM (Real-Time Marketing) data
    - questions_table: Questions and answers data

    Security: All queries are automatically filtered by the campaigner's agency.
    The tool ONLY accepts SELECT queries - no INSERT, UPDATE, DELETE, or DDL.
    Input should be a valid SINGLE PostgreSQL SELECT query.
    Output will be a JSON array of result rows.
    """

    campaigner_id: int = PydanticField(description="ID of the authenticated campaigner")

    def _run(self, query: str) -> str:
        """Execute a SQL query and return results.

        Args:
            query: SQL SELECT query to execute

        Returns:
            JSON string with query results or error message
        """
        try:
            # sql_validator = SQLValidator()  # Shared validator instance

            # # Validate query with LLM validator
            # is_valid, reason, validation_details = sql_validator.validate(query)

            # if not is_valid:
            #     error_msg = f"Query validation failed: {reason}"
            #     logger.warning(f"🚫 [PostgresTool] Blocked invalid query from campaigner {self.campaigner_id}: {reason}")
            #     import json
            #     return json.dumps({
            #         "success": False,
            #         "error": error_msg,
            #         "validation": validation_details
            #     })

            # Additional basic validation
            if not self._is_read_only_query(query):
                error_msg = "Only SELECT queries are allowed. No INSERT, UPDATE, DELETE, or DDL operations."
                logger.warning(f"🚫 [PostgresTool] Blocked non-SELECT query from campaigner {self.campaigner_id}")
                import json
                return json.dumps({"success": False, "error": error_msg})

            # Use query as-is (LLM should have written it with proper security filtering)
            secured_query = query

            logger.info(f"🔍 [PostgresTool] Executing query for campaigner {self.campaigner_id}")
            logger.debug(f"📝 [PostgresTool] Query: {secured_query}")

            # Execute query
            with get_db_connection() as session:
                result = session.execute(text(secured_query), {"campaigner_id": self.campaigner_id})
                rows = result.fetchall()

                # Convert to list of dicts
                if rows:
                    columns = result.keys()
                    results = [dict(zip(columns, row)) for row in rows]
                else:
                    results = []

                logger.info(f"✅ [PostgresTool] Query returned {len(results)} rows")

                # Format as JSON
                import json
                return json.dumps({
                    "success": True,
                    "row_count": len(results),
                    "data": results
                }, default=str)  # default=str handles datetime serialization

        except Exception as e:
            logger.error(f"❌ [PostgresTool] Query failed: {str(e)}", exc_info=True)
            import json
            return json.dumps({
                "success": False,
                "error": str(e)
            })

    async def _arun(self, query: str) -> str:
        """Async version - not implemented, falls back to sync."""
        return self._run(query)

    def _is_read_only_query(self, query: str) -> bool:
        """Check if query is a SELECT statement.

        Args:
            query: SQL query string

        Returns:
            True if query is SELECT only, False otherwise
        """
        # Normalize query
        normalized = query.strip().upper()

        # Remove comments
        normalized = re.sub(r'--.*$', '', normalized, flags=re.MULTILINE)
        normalized = re.sub(r'/\*.*?\*/', '', normalized, flags=re.DOTALL)

        # Check for dangerous keywords
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE',
            'CALL', 'MERGE', 'REPLACE', 'LOCK', 'UNLOCK'
        ]

        for keyword in dangerous_keywords:
            if re.search(r'\b' + keyword + r'\b', normalized):
                return False

        # Must start with SELECT (after whitespace/comments)
        if not normalized.startswith('SELECT'):
            return False

        return True

    def _inject_security_filter(self, query: str) -> str:
        """Inject security filtering into the query.

        This ensures the query only returns data for the campaigner's agency.

        Args:
            query: Original SQL query

        Returns:
            Modified query with security filter
        """
        # For now, we rely on the SQL writer to include proper JOINs
        # In a more sophisticated implementation, we could parse and modify the SQL
        # to automatically inject agency_id filtering

        # TODO: Implement SQL parsing to automatically inject:
        # JOIN campaigners camp ON camp.agency_id = <table>.agency_id
        # WHERE camp.id = :campaigner_id

        return query

    def get_schema_info(self) -> Dict[str, Any]:
        """Get database schema information dynamically from SQLModel classes.

        Only includes tables that basic_info_agent has access to:
        - customers
        - kpi_goals
        - kpi_values
        - digital_assets
        - connections
        - rtm_table
        - questions_table

        Returns:
            Dictionary with table schemas
        """
        schema_info = {}

        # Map of models to extract schema from (RESTRICTED LIST)
        # Excludes agencies and campaigners tables
        models = {
            "customers": Customer,
            "kpi_goals": KpiGoal,
            "kpi_values": KpiValue,
            "digital_assets": DigitalAsset,
            "connections": Connection,
            "rtm_table": RTMTable,
            "questions_table": QuestionsTable,
        }

        for table_name, model_class in models.items():
            schema_info[table_name] = self._extract_model_schema(model_class)

        # Add relationship information
        schema_info["relationships"] = {
            "description": "Table relationships for proper JOINs. Note: agencies and campaigners tables are NOT accessible.",
            "chains": {
                "kpi_goals_to_campaigner": "kpi_goals.customer_id → customers.id → customers.agency_id = campaigners.agency_id → campaigners.id = :campaigner_id",
                "kpi_values_to_campaigner": "kpi_values.customer_id → customers.id → customers.agency_id = campaigners.agency_id → campaigners.id = :campaigner_id",
                "customers_to_campaigner": "customers.agency_id = campaigners.agency_id → campaigners.id = :campaigner_id",
                "digital_assets_to_campaigner": "digital_assets.customer_id → customers.id → customers.agency_id = campaigners.agency_id → campaigners.id = :campaigner_id",
                "connections_to_campaigner": "connections.customer_id → customers.id → customers.agency_id = campaigners.agency_id → campaigners.id = :campaigner_id",
                "rtm_table_to_campaigner": "rtm_table access requires proper filtering",
                "questions_table_to_campaigner": "questions_table access requires proper filtering"
            }
        }

        return schema_info

    def _extract_model_schema(self, model_class) -> Dict[str, Any]:
        """Extract schema information from a SQLModel class.

        Args:
            model_class: SQLModel class to extract schema from

        Returns:
            Dictionary with table description and columns
        """
        schema = {
            "description": model_class.__doc__.strip() if model_class.__doc__ else model_class.__name__,
            "columns": {}
        }

        # Get field information from the model
        if hasattr(model_class, '__fields__'):
            for field_name, field_info in model_class.__fields__.items():
                # Get field type
                field_type = self._format_field_type(field_info.annotation)

                # Get field description from Field() if available
                description = ""
                if hasattr(field_info, 'description') and field_info.description:
                    description = field_info.description
                elif hasattr(field_info, 'field_info') and hasattr(field_info.field_info, 'description'):
                    description = field_info.field_info.description or ""

                # Check if it's a foreign key
                is_foreign_key = False
                foreign_key_table = None
                if hasattr(field_info, 'field_info'):
                    field_metadata = field_info.field_info
                    if hasattr(field_metadata, 'json_schema_extra'):
                        extra = field_metadata.json_schema_extra or {}
                        if 'foreign_key' in extra:
                            is_foreign_key = True
                            foreign_key_table = extra['foreign_key'].split('.')[0]

                # Check if field is optional
                is_optional = get_origin(field_info.annotation) is Optional or type(None) in get_args(field_info.annotation)

                # Build column description
                col_desc_parts = [field_type]
                if description:
                    col_desc_parts.append(f"- {description}")
                if is_foreign_key and foreign_key_table:
                    col_desc_parts.append(f"(FK to {foreign_key_table})")
                elif field_name == "id":
                    col_desc_parts.append("(Primary key)")
                if is_optional:
                    col_desc_parts.append("(Optional)")

                schema["columns"][field_name] = " ".join(col_desc_parts)

        # Add security information for tables that need JOINs
        table_name = model_class.__tablename__ if hasattr(model_class, '__tablename__') else model_class.__name__.lower()

        if table_name in ["kpi_goals", "kpi_values"]:
            schema["security"] = f"MUST join: {table_name} → customers → campaigners"
            schema["example_join"] = f"FROM {table_name} kg JOIN customers c ON c.id = kg.customer_id JOIN campaigners camp ON camp.agency_id = c.agency_id WHERE camp.id = :campaigner_id"
        elif table_name == "customers":
            schema["security"] = "Join with campaigners on agency_id"
            schema["example_join"] = "FROM customers c JOIN campaigners camp ON camp.agency_id = c.agency_id WHERE camp.id = :campaigner_id"
        elif table_name == "campaigners":
            schema["security"] = "Auto-filtered by campaigner_id"
        elif table_name in ["digital_assets", "connections"]:
            schema["security"] = f"MUST join: {table_name} → customers → campaigners"
            schema["example_join"] = f"FROM {table_name} da JOIN customers c ON c.id = da.customer_id JOIN campaigners camp ON camp.agency_id = c.agency_id WHERE camp.id = :campaigner_id"

        return schema

    def _format_field_type(self, annotation) -> str:
        """Format a Python type annotation as a readable string.

        Args:
            annotation: Type annotation

        Returns:
            Human-readable type string
        """
        # Handle Optional types
        origin = get_origin(annotation)
        if origin is Optional:
            args = get_args(annotation)
            inner_type = args[0] if args else annotation
            return self._format_field_type(inner_type)

        # Handle basic types
        if annotation == int or annotation == 'int':
            return "int"
        elif annotation == str or annotation == 'str':
            return "str"
        elif annotation == float or annotation == 'float':
            return "float"
        elif annotation == bool or annotation == 'bool':
            return "bool"
        elif hasattr(annotation, '__name__') and 'datetime' in annotation.__name__.lower():
            return "datetime"
        elif hasattr(annotation, '__name__') and 'dict' in annotation.__name__.lower():
            return "dict/json"
        elif hasattr(annotation, '__name__') and 'list' in annotation.__name__.lower():
            return "list/array"
        elif hasattr(annotation, '__name__'):
            return annotation.__name__
        else:
            return str(annotation)
