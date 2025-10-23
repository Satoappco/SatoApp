"""SQL query validator using LLM."""

import logging
import re
from typing import Dict, Any, Tuple
from langchain_core.messages import SystemMessage, HumanMessage
# from langchain_openai import ChatOpenAI
# from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


class SQLValidator:
    """Validates SQL queries for safety and correctness using an LLM."""

    def __init__(self, llm: BaseChatModel = None):
        """Initialize the SQL validator.

        Args:
            llm: Language model for validation (defaults to gpt-4o-mini)
        """
        self.llm = llm or ChatGoogleGenerativeAI(model="gemini-2.5-flash") #ChatAnthropic(model='claude-3-opus-20240229') #ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.system_prompt = """You are a strict SQL security validator.

Your job is to analyze SQL queries and ensure they are:
1. READ-ONLY (SELECT queries only)
2. Properly secured with agency-level filtering
3. Free from SQL injection vulnerabilities
4. Syntactically correct PostgreSQL

REQUIRED SECURITY PATTERN:
Every query accessing customer/campaign data MUST include a JOIN to the campaigners table
with filtering by :campaigner_id parameter.

Valid patterns:
1. For kpi_goals or kpi_values (via customers):
```sql
FROM kpi_goals kg
JOIN customers c ON c.id = kg.customer_id
JOIN campaigners camp ON camp.agency_id = c.agency_id
WHERE camp.id = :campaigner_id
```

2. For customers table (direct):
```sql
FROM customers c
JOIN campaigners camp ON camp.agency_id = c.agency_id
WHERE camp.id = :campaigner_id
```

3. For agencies or campaigners table:
```sql
FROM campaigners WHERE id = :campaigner_id
-- or --
FROM agencies a JOIN campaigners c ON c.agency_id = a.id WHERE c.id = :campaigner_id
```

The key requirement is: WHERE clause MUST contain `camp.id = :campaigner_id` or equivalent.

FORBIDDEN:
- INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE
- GRANT, REVOKE, EXEC, EXECUTE, CALL
- Multiple statements (semicolons)
- Comments that might hide malicious code
- Dynamic SQL or string concatenation
- Subqueries that bypass security filtering

Respond with JSON:
```json
{
  "valid": true|false,
  "reason": "explanation of validation result",
  "security_score": 0-100,
  "suggestions": ["optional suggestions for improvement"]
}
```
"""

    def validate(self, query: str, context: Dict[str, Any] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """Validate a SQL query for safety and correctness.

        Args:
            query: SQL query string to validate
            context: Additional context about the query

        Returns:
            Tuple of (is_valid, reason, validation_details)
        """
        logger.info("🔍 [SQLValidator] Validating query")
        logger.debug(f"📝 [SQLValidator] Query: {query[:200]}...")

        try:
            # Quick pre-checks
            if not self._basic_validation(query):
                return False, "Failed basic validation checks", {"security_score": 0}

            # LLM-based validation
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=f"""Validate this SQL query:

```sql
{query}
```

Context: Query will be executed with campaigner_id parameter for security filtering.
""")
            ]

            response = self.llm.invoke(messages)
            logger.debug(f"💭 [SQLValidator] LLM response: {response.content[:200]}...")

            # Parse response
            import json
            # Extract JSON from markdown code blocks if present
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            validation_result = json.loads(content)

            is_valid = validation_result.get("valid", False)
            reason = validation_result.get("reason", "No reason provided")

            if is_valid:
                logger.info(f"✅ [SQLValidator] Query validated successfully (score: {validation_result.get('security_score', 'N/A')})")
            else:
                logger.warning(f"🚫 [SQLValidator] Query rejected: {reason}")

            return is_valid, reason, validation_result

        except Exception as e:
            logger.error(f"❌ [SQLValidator] Validation error: {str(e)}", exc_info=True)
            return False, f"Validation failed: {str(e)}", {"security_score": 0}

    def _basic_validation(self, query: str) -> bool:
        """Perform basic regex-based validation.

        Args:
            query: SQL query string

        Returns:
            True if passes basic checks, False otherwise
        """
        if not query or not query.strip():
            logger.warning("🚫 [SQLValidator] Empty query")
            return False

        normalized = query.strip().upper()

        # Remove comments for analysis
        normalized = re.sub(r'--.*$', '', normalized, flags=re.MULTILINE)
        normalized = re.sub(r'/\*.*?\*/', '', normalized, flags=re.DOTALL)

        # Must start with SELECT
        if not normalized.startswith('SELECT'):
            logger.warning("🚫 [SQLValidator] Query does not start with SELECT")
            return False

        # Check for dangerous keywords
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE',
            'CALL', 'MERGE', 'REPLACE', 'LOCK', 'UNLOCK', 'SET '
        ]

        for keyword in dangerous_keywords:
            if re.search(r'\b' + keyword + r'\b', normalized):
                logger.warning(f"🚫 [SQLValidator] Dangerous keyword found: {keyword}")
                return False

        # Check for multiple statements
        if ';' in query.rstrip(';'):  # Allow trailing semicolon
            logger.warning("🚫 [SQLValidator] Multiple statements detected")
            return False

        return True
