"""SQL-based BasicInfoAgent using LangChain tools."""

import logging
import json
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from ..tools.postgres_tool import PostgresTool
from app.services.agent_service import AgentService

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

    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.validator_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash") #ChatOpenAI(model="gpt-4o-mini", temperature=0)  # Dedicated validator
        self.agent_service = AgentService()

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

        # Add language instruction
        user_language = context.get("language", "hebrew")
        language_name = "Hebrew" if user_language == "hebrew" else "English"
        context_parts.append(f"\nIMPORTANT: User's language is {language_name}. Respond in {language_name}.")

        context_str = "\n".join(context_parts) if context_parts else ""

        # Load system message from database or use fallback
        system_message = self._load_system_prompt(schema_str, context_str)
        logger.debug(f"📜 [SQLBasicInfoAgent] System prompt loaded: \n{system_message}")

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

    def _load_system_prompt(self, schema_str: str, context_str: str) -> str:
        """Load SQL agent system prompt from database or use fallback.

        Args:
            schema_str: Formatted database schema string
            context_str: Formatted context string

        Returns:
            System prompt string
        """
        try:
            # Try to get SQL agent config from database
            sql_agent_config = self.agent_service.get_agent_config("sql_database_expert")

            if sql_agent_config:
                logger.info("✅ Loaded SQL database expert config from database")

                # Build system prompt from database config
                role = sql_agent_config.get('role', 'SQL database assistant')
                goal = sql_agent_config.get('goal', '')
                backstory = sql_agent_config.get('backstory', '')
                task_template = sql_agent_config.get('task', '')

                # Build the system message
                prompt_parts = []
                if role:
                    prompt_parts.append(f"{role}.")
                if backstory:
                    prompt_parts.append(f"\n{backstory}")
                if goal:
                    prompt_parts.append(f"\nYour goal: {goal}")

                # Add schema and context
                prompt_parts.append(f"\nDatabase Schema:\n```json\n{schema_str}\n```")
                if context_str:
                    prompt_parts.append(f"\n{context_str}")

                # Add task instructions
                if task_template:
                    prompt_parts.append(f"\n{task_template}")

                return "\n".join(prompt_parts)
            else:
                logger.warning("⚠️  SQL database expert config not found in database, using fallback")
                return self._get_fallback_prompt(schema_str, context_str)

        except Exception as e:
            logger.error(f"❌ Failed to load SQL agent config from database: {e}")
            return self._get_fallback_prompt(schema_str, context_str)

    def _get_fallback_prompt(self, schema_str: str, context_str: str) -> str:
        """Fallback system prompt if database config is not available.

        Args:
            schema_str: Formatted database schema string
            context_str: Formatted context string

        Returns:
            Fallback system prompt
        """
        return """
You are an expert SQL database assistant with READ-ONLY access to a PostgreSQL database.

Your role is to:
1. Understand the user's question
2. Write efficient SELECT queries to retrieve the needed data
3. Execute queries using the postgres_query tool
4. Interpret results and provide clear answers
5. **ALWAYS respond in the language specified in the context below**

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
7. Only a single SQL query is allowed, DO NOT use semicolon(;) in the query
8. campaigner_id parameter is known as :campaigner_id and will be provided at execution time, DO NOT hardcode any IDs

When answering:
- Be specific and reference actual data from query results
- Format lists and tables clearly
- Include relevant IDs
- If no data found, explain what was searched
- Present data clearly using bullet points or lists when appropriate
- Use ** for bold emphasis on important information
- Keep responses concise but informative
- If no data was found, acknowledge it and suggest alternatives

"""

            # 4. Return structured data summary for the chatbot to present to the user
            # 5. **ALWAYS respond in the same language as the user's query** (Hebrew/English/etc.)

            # IMPORTANT: You are a data retrieval tool. Your response will be processed by a chatbot that handles the conversation with the user. Focus on:
            # - Executing accurate queries
            # - Returning clear, structured data summaries
            # - Providing brief context about what data was found
            # - DO NOT try to be conversational or handle language - the chatbot will do that

            # Response Format:
            # Provide a brief, factual summary of the data retrieved. For example:
            # - "Found 5 customers with 23 total campaigns, 15 active"
            # - "Retrieved campaign 'Summer Sale' with budget $1000, status: ACTIVE"
            # - "No active campaigns found for customer XYZ"

            # Keep it concise and factual. The chatbot will handle the conversational aspects and language.