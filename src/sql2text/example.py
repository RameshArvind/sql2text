import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from agents import Agent, Runner
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _find_mcp_config_path(explicit_path: Optional[str] = None) -> Optional[str]:
    """Find the mcp-config.json path.

    Order of precedence:
    1) explicit path provided
    2) current working directory
    3) project root (three parents up from this file)
    """
    if explicit_path:
        p = Path(explicit_path)
        if p.is_file():
            return str(p)

    cwd_candidate = Path.cwd() / "mcp-config.json"
    if cwd_candidate.is_file():
        return str(cwd_candidate)

    project_root_candidate = Path(__file__).resolve().parents[2] / "mcp-config.json"
    if project_root_candidate.is_file():
        return str(project_root_candidate)

    return None


def _collect_clickhouse_env_from_os() -> Dict[str, str]:
    """Collect CLICKHOUSE_* environment variables from the OS."""
    return {k: v for k, v in os.environ.items() if k.startswith("CLICKHOUSE_")}


def load_mcp_server_params(
    server_name: str = "mcp-clickhouse", config_path: Optional[str] = None
) -> StdioServerParameters:
    """Create StdioServerParameters from mcp-config.json or environment.

    - If mcp-config.json exists and contains the server, use its command/args/env.
    - Overlay any CLICKHOUSE_* values from the current environment (env overrides file).
    - If no config is found, fall back to a sensible default using uvx and only OS env.
    """
    path = _find_mcp_config_path(config_path or os.environ.get("MCP_CONFIG_PATH"))

    command: str = "uvx"
    args: List[str] = ["--python", "3.10", server_name]
    env: Dict[str, str] = {}

    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            servers = cfg.get("mcpServers", {})
            server_cfg = servers.get(server_name)
            if server_cfg:
                command = server_cfg.get("command", command)
                args = server_cfg.get("args", args)
                file_env = server_cfg.get("env", {}) or {}
                env.update(file_env)
        except Exception:
            # Silently fall back to defaults if config parsing fails
            pass

    # Overlay with OS environment CLICKHOUSE_* (take precedence)
    env.update(_collect_clickhouse_env_from_os())

    return StdioServerParameters(command=command, args=args, env=env)


def load_mcp_http_url(
    server_name: str = "clickhouse-remote", config_path: Optional[str] = None
) -> Optional[str]:
    """Return remote MCP server URL from config or env if available.

    Order of precedence:
    1) MCP_URL env var
    2) mcp-config.json -> mcpServers[server_name].url
    """
    # Highest precedence: explicit env var
    url_env = os.environ.get("MCP_URL")
    if url_env:
        return url_env

    path = _find_mcp_config_path(config_path or os.environ.get("MCP_CONFIG_PATH"))
    if not path:
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        servers = cfg.get("mcpServers", {})
        server_cfg = servers.get(server_name, {})
        url = server_cfg.get("url")
        if isinstance(url, str) and url.strip():
            return url
    except Exception:
        pass

    return None


class MCPClickHouseClient:
    """Client that communicates with ClickHouse through MCP server."""

    def __init__(self, server_params: Optional[StdioServerParameters] = None):
        self.session = None
        self._server_params = server_params

    async def connect(self):
        """Connect to the MCP ClickHouse server using config-first settings."""
        try:
            # Prefer remote HTTP URL if configured; otherwise fall back to stdio
            http_url = load_mcp_http_url()
            if http_url:
                # Try HTTP client first (if supported by mcp)
                try:
                    from mcp.client.http import http_client  # type: ignore

                    async with http_client(http_url) as (read, write):
                        async with ClientSession(read, write) as session:
                            self.session = session
                            print(
                                "✅ Connected to ClickHouse Remote MCP server (HTTP)!"
                            )
                            return
                except Exception:
                    # Try SSE client fallback if available
                    try:
                        from mcp.client.sse import sse_client  # type: ignore

                        async with sse_client(http_url) as (read, write):
                            async with ClientSession(read, write) as session:
                                self.session = session
                                print(
                                    "✅ Connected to ClickHouse Remote MCP server (SSE)!"
                                )
                                return
                    except Exception as e:
                        print(
                            f"⚠️  Remote MCP connection failed, falling back to stdio: {e}"
                        )

            server_params = self._server_params or load_mcp_server_params(
                server_name="mcp-clickhouse"
            )

            # Connect to the MCP server via stdio
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.session = session
                    print("✅ Connected to ClickHouse MCP server (stdio) successfully!")

        except Exception as e:
            print(f"❌ Failed to connect to MCP ClickHouse server: {e}")
            raise

    async def execute_query(self, sql: str) -> List[Dict]:
        """Execute SQL query through MCP server and return results."""
        if not self.session:
            await self.connect()

        try:
            # Use the MCP server's query execution capability
            result = await self.session.call_tool("execute_query", {"sql": sql})
            return result.content[0].text if result.content else []
        except Exception as e:
            print(f"❌ Query execution failed: {e}")
            raise

    async def get_table_schema(self, table_name: str) -> str:
        """Get schema information for a table through MCP server."""
        try:
            result = await self.session.call_tool(
                "describe_table", {"table_name": table_name}
            )
            return (
                result.content[0].text
                if result.content
                else f"Could not retrieve schema for {table_name}"
            )
        except Exception as e:
            return f"Could not retrieve schema for {table_name}: {e}"

    async def get_sample_data(self, table_name: str, limit: int = 5) -> str:
        """Get sample data from a table through MCP server."""
        try:
            result = await self.session.call_tool(
                "sample_data", {"table_name": table_name, "limit": limit}
            )
            return (
                result.content[0].text
                if result.content
                else f"No data found in table '{table_name}'"
            )
        except Exception as e:
            return f"Could not retrieve sample data from {table_name}: {e}"

    async def list_tables(self) -> List[str]:
        """List available tables through MCP server."""
        try:
            result = await self.session.call_tool("list_tables", {})
            if result.content:
                return json.loads(result.content[0].text)
            return []
        except Exception as e:
            print(f"❌ Failed to list tables: {e}")
            return []


# Create specialized agents for different SQL-to-text tasks
sql_analyzer_agent = Agent(
    name="SQL Analyzer",
    instructions="""You are an expert SQL analyst. Your job is to:
    1. Analyze SQL queries and explain what they do in plain English
    2. Identify the tables, columns, and operations involved
    3. Explain the business logic and purpose of the query
    4. Highlight any potential performance issues or best practices
    5. Provide suggestions for optimization if applicable
    
    Always be clear, concise, and use business-friendly language.""",
)

data_explorer_agent = Agent(
    name="Data Explorer",
    instructions="""You are a data exploration specialist. Your job is to:
    1. Help users understand their data structure and content
    2. Suggest relevant queries based on their questions
    3. Explain data relationships and patterns
    4. Provide insights about data quality and completeness
    5. Recommend next steps for analysis
    
    Focus on making data accessible and actionable for business users.""",
)

query_optimizer_agent = Agent(
    name="Query Optimizer",
    instructions="""You are a ClickHouse performance expert. Your job is to:
    1. Analyze query performance and identify bottlenecks
    2. Suggest indexing strategies and query optimizations
    3. Recommend ClickHouse-specific best practices
    4. Explain how different query patterns affect performance
    5. Provide alternative query approaches when appropriate
    
    Focus on ClickHouse-specific optimizations and performance tuning.""",
)

# Main SQL-to-text agent that coordinates with others
sql2text_agent = Agent(
    name="SQL2Text Coordinator",
    instructions="""You coordinate SQL-to-text conversion by:
    1. Understanding what the user wants to know about their SQL or data
    2. Deciding which specialist agent to use (analyzer, explorer, or optimizer)
    3. Gathering necessary context from ClickHouse when needed
    4. Presenting clear, actionable insights to the user
    
    Always provide context about the data and explain your reasoning.""",
    handoffs=[sql_analyzer_agent, data_explorer_agent, query_optimizer_agent],
)


async def demonstrate_clickhouse_sql2text():
    """Demonstrate SQL-to-text conversion using ClickHouse MCP server."""

    # Initialize the MCP ClickHouse client
    mcp_client = MCPClickHouseClient()

    try:
        # Connect to MCP server
        await mcp_client.connect()

        # Example 1: Analyze a simple query
        print("=" * 60)
        print("EXAMPLE 1: Analyzing a simple SQL query")
        print("=" * 60)

        simple_query = "SELECT COUNT(*) as total_users FROM system.users"
        print(f"SQL Query: {simple_query}")

        # Execute the query to get context
        result = await mcp_client.execute_query(simple_query)
        context = f"Query result: {result[0] if result else 'No result'}"

        # Use the agent to explain the query
        analysis_prompt = f"""
        Please analyze this SQL query and explain what it does:
        
        Query: {simple_query}
        Result: {context}
        
        Explain:
        1. What this query does
        2. What the result means
        3. When you might use this type of query
        """

        analysis_result = await Runner.run(sql_analyzer_agent, input=analysis_prompt)
        print(f"\nAnalysis: {analysis_result.final_output}")

        # Example 2: Explore available data
        print("\n" + "=" * 60)
        print("EXAMPLE 2: Exploring available data")
        print("=" * 60)

        # Get list of tables through MCP
        available_tables = await mcp_client.list_tables()
        if available_tables:
            available_tables = available_tables[:5]  # First 5 tables

        exploration_prompt = f"""
        The user wants to explore their ClickHouse database. Here are some available system tables:
        {available_tables}
        
        Help them understand:
        1. What these tables contain
        2. Which ones might be useful for different types of analysis
        3. Suggest some interesting queries they could run
        """

        exploration_result = await Runner.run(
            data_explorer_agent, input=exploration_prompt
        )
        print(f"Data Exploration Guide: {exploration_result.final_output}")

        # Example 3: Query optimization
        print("\n" + "=" * 60)
        print("EXAMPLE 3: Query optimization advice")
        print("=" * 60)

        complex_query = """
        SELECT 
            database,
            table,
            COUNT(*) as column_count
        FROM system.columns 
        WHERE database != 'system'
        GROUP BY database, table
        ORDER BY column_count DESC
        LIMIT 10
        """

        optimization_prompt = f"""
        Please analyze this ClickHouse query for performance and provide optimization suggestions:
        
        Query: {complex_query}
        
        Focus on:
        1. Performance characteristics
        2. ClickHouse-specific optimizations
        3. Potential bottlenecks
        4. Alternative approaches
        """

        optimization_result = await Runner.run(
            query_optimizer_agent, input=optimization_prompt
        )
        print(f"Optimization Analysis: {optimization_result.final_output}")

    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        print(
            "Note: Make sure the MCP ClickHouse server is properly configured and accessible."
        )

    finally:
        # MCP client cleanup is handled by the context manager
        pass


async def demonstrate_linkup_remote_mcp():
    """Demonstrate connecting to Linkup Remote MCP and performing a sample search.

    Configuration options (order of precedence):
    1) `mcp-config.json` -> `mcpServers.linkup.url`
    2) `MCP_URL` env var
    3) `LINKUP_API_KEY` env var (constructs https://mcp.linkup.so/sse?apiKey=...)
    """
    # Resolve Linkup MCP URL
    url = load_mcp_http_url(server_name="linkup")
    if not url:
        api_key = os.environ.get("LINKUP_API_KEY")
        if api_key:
            url = f"https://mcp.linkup.so/sse?apiKey={api_key}"

    if not url:
        print(
            "ℹ️ Linkup Remote MCP not configured. Set `mcpServers.linkup.url` in mcp-config.json "
            "or export LINKUP_API_KEY to construct the URL. See docs: https://docs.linkup.so/pages/integrations/mcp/mcp#remote-mcp"
        )
        return

    try:
        # Import SSE client only when needed
        from mcp.client.sse import sse_client  # type: ignore

        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                print("✅ Connected to Linkup Remote MCP (SSE)")

                # Try calling the Linkup search tool
                sample_query = "Latest updates about the Model Context Protocol; include 3 citations."
                try:
                    result = await session.call_tool("search", {"query": sample_query})
                    preview = (
                        result.content[0].text[:500]
                        if result.content
                        else "<no content>"
                    )
                    print("\n🔎 Linkup Search result (preview):\n" + preview)
                except Exception as e:
                    print(
                        f"⚠️ Could not call 'search' tool on Linkup MCP (this may vary by account/plan): {e}"
                    )
    except Exception as e:
        print(f"❌ Failed to connect to Linkup Remote MCP: {e}")


async def interactive_sql2text():
    """Interactive SQL-to-text conversion using MCP server."""
    mcp_client = MCPClickHouseClient()

    try:
        await mcp_client.connect()

        print("🔍 Interactive SQL-to-Text Converter (via MCP)")
        print("Type 'quit' to exit, 'help' for commands")
        print("-" * 50)

        while True:
            user_input = input("\n> ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                break
            elif user_input.lower() == "help":
                print("""
Available commands:
- Ask about a SQL query (e.g., "What does this query do: SELECT * FROM users")
- Request data exploration (e.g., "Show me what tables are available")
- Ask for optimization advice (e.g., "How can I optimize this query")
- Execute a query (e.g., "Run: SELECT COUNT(*) FROM system.tables")
- Type 'quit' to exit
                """)
                continue
            elif not user_input:
                continue

            # Check if user wants to execute a query directly
            if user_input.lower().startswith("run:"):
                query = user_input[4:].strip()
                try:
                    result = await mcp_client.execute_query(query)
                    print(f"Query result: {result}")
                except Exception as e:
                    print(f"Query failed: {e}")
                continue

            # Use the coordinator agent to handle the request
            result = await Runner.run(
                sql2text_agent,
                input=f"User request: {user_input}\n\nPlease help with this SQL or data-related question.",
            )
            print(f"\n{result.final_output}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # MCP client cleanup is handled by the context manager
        pass


async def main():
    """Main function to run examples."""
    print("🚀 SQL2Text with ClickHouse MCP Server")
    print("=" * 50)

    # Run demonstration
    await demonstrate_clickhouse_sql2text()

    # Ask if user wants interactive mode
    print("\n" + "=" * 60)
    response = input("Would you like to try interactive mode? (y/n): ").strip().lower()
    if response in ["y", "yes"]:
        await interactive_sql2text()


if __name__ == "__main__":
    asyncio.run(main())
