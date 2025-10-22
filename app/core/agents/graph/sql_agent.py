"""SQL-based BasicInfoAgent using LangChain tools."""

import logging
import json
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from ..tools.postgres_tool import PostgresTool

logger = logging.getLogger(__name__)


class SQLBasicInfoAgent:
    """SQL Expert Agent that generates and executes database queries.

    This agent:
    1. Analyzes the user's question
    2. Generates appropriate SQL SELECT queries
    3. The SQL is validated by another LLM
    4. Executes validated queries via PostgresTool
    5. Interprets results and answers in the user's language
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.validator_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)  # Dedicated validator

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a database query task.

        Args:
            task: Dictionary containing:
                - query: The user's question
                - campaigner_id: ID of the authenticated user (REQUIRED)
                - context: Optional additional context

        Returns:
            Dictionary containing the result
        """
        query = task.get("query", "")
        campaigner_id = task.get("campaigner_id")
        context = task.get("context", {})

        logger.info(f"🤖 [SQLBasicInfoAgent] Processing query for campaigner: {campaigner_id}")
        logger.debug(f"📝 [SQLBasicInfoAgent] Query: '{query[:100]}...'")

        # Validate campaigner_id
        if not campaigner_id:
            logger.error("❌ [SQLBasicInfoAgent] No campaigner_id provided")
            return {
                "status": "error",
                "result": "Authentication required. No campaigner ID provided.",
                "agent": "basic_info_agent",
            }

        try:
            # Create PostgresTool instance
            postgres_tool = PostgresTool(campaigner_id=campaigner_id)

            # Get schema information
            schema_info = postgres_tool.get_schema_info()

            # Create the agent with tools
            agent = self._create_agent(postgres_tool, schema_info, context)

            # Execute the agent
            logger.info(f"🚀 [SQLBasicInfoAgent] Executing agent")
            result = agent.invoke({
                "input": query,
                "chat_history": []
            })

            logger.info(f"✅ [SQLBasicInfoAgent] Agent completed")
            logger.debug(f"💬 [SQLBasicInfoAgent] Output: {result['output'][:200]}...")

            return {
                "status": "completed",
                "result": result["output"],
                "agent": "basic_info_agent",
            }

        except Exception as e:
            logger.error(f"❌ [SQLBasicInfoAgent] Error: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "result": f"An error occurred while processing your request: {str(e)}",
                "agent": "basic_info_agent",
            }

    def _create_agent(
        self,
        postgres_tool: PostgresTool,
        schema_info: Dict[str, Any],
        context: Dict[str, Any]
    ) -> AgentExecutor:
        """Create a LangChain agent with PostgresTool.

        Args:
            postgres_tool: PostgreSQL query tool
            schema_info: Database schema information
            context: Additional context (agency info, etc.)

        Returns:
            Configured AgentExecutor
        """
        # Format schema for prompt - escape curly braces for LangChain template
        schema_str = json.dumps(schema_info, indent=2).replace("{", "{{").replace("}", "}}")

        # Format context from ChatbotNode
        context_parts = []
        if context.get("agency"):
            agency = context["agency"]
            context_parts.append(f"Agency: {agency.get('name')} (ID: {agency.get('id')}), Status: {agency.get('status')}")
        if context.get("campaigner"):
            camp = context["campaigner"]
            context_parts.append(f"User: {camp.get('full_name')} ({camp.get('email')}), Role: {camp.get('role')}")

        context_str = "\n".join(context_parts) if context_parts else ""

        # Build the system message with proper escaping
        system_message = """You are an expert SQL database assistant with READ-ONLY access to a PostgreSQL database.

Your role is to:
1. Understand the user's question
2. Write efficient SELECT queries to retrieve the needed data
3. Execute queries using the postgres_query tool
4. Interpret results and provide clear answers
5. **ALWAYS respond in the same language as the user's query** (Hebrew/English/etc.)

Database Schema:
```json
""" + schema_str + """
```

""" + context_str + """



IMPORTANT SQL WRITING RULES:
1. ALL queries MUST include security filtering with proper JOINs:

   **For kpi_goals or kpi_values tables:**
   - These tables do NOT have agency_id directly
   - MUST join through customers table:
   ```sql
   FROM kpi_goals kg
   JOIN customers c ON c.id = kg.customer_id
   JOIN campaigners camp ON camp.agency_id = c.agency_id
   WHERE camp.id = :campaigner_id
   ```

   **For customers table:**
   - Join directly with campaigners:
   ```sql
   FROM customers c
   JOIN campaigners camp ON camp.agency_id = c.agency_id
   WHERE camp.id = :campaigner_id
   ```

   **For agencies or campaigners table:**
   - Filter by campaigner_id directly

2. Example secure query for campaigns:
```sql
SELECT DISTINCT kg.campaign_id, kg.campaign_name, kg.campaign_status,
       c.full_name as customer_name
FROM kpi_goals kg
JOIN customers c ON c.id = kg.customer_id
JOIN campaigners camp ON camp.agency_id = c.agency_id
WHERE camp.id = :campaigner_id
  AND kg.campaign_status = 'ACTIVE'
LIMIT 20
```

3. Only use SELECT queries - no INSERT, UPDATE, DELETE, DROP or DDL
4. Use proper JOINs to ensure security filtering
5. Include LIMIT clauses to prevent large result sets (max 100 rows)
6. Use meaningful column aliases for clarity

When answering:
- Be specific and reference actual data from query results
- Format lists and tables clearly
- Include relevant IDs
- If no data found, explain what was searched
- Respond in the user's language
"""

        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # Create tool-calling agent
        agent = create_tool_calling_agent(
            llm=self.llm,
            tools=[postgres_tool],
            prompt=prompt
        )

        # Create agent executor
        agent_executor = AgentExecutor(
            agent=agent,
            tools=[postgres_tool],
            verbose=True,
            max_iterations=5,
            handle_parsing_errors=True,
            return_intermediate_steps=False
        )

        return agent_executor
