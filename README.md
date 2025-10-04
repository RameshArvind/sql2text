# SQL2Text with ClickHouse MCP Server

A powerful tool that converts SQL queries to natural language descriptions using ClickHouse as the data source and AI agents for intelligent analysis.

## Features

- 🔍 **SQL Query Analysis**: Convert complex SQL queries into plain English explanations
- 📊 **Data Exploration**: Interactive exploration of ClickHouse databases with AI-powered insights
- ⚡ **Query Optimization**: Get ClickHouse-specific performance recommendations
- 🤖 **Multi-Agent System**: Specialized AI agents for different analysis tasks
- 🔗 **MCP Integration**: Seamless integration with Model Context Protocol (MCP) servers
- 🚀 **Zero Installation**: Uses `uvx` to run MCP servers on-demand without permanent installation

## Quick Start

### Prerequisites

- Python 3.13+
- UV package manager
- Access to a ClickHouse server

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd sql2text
```

2. Install dependencies:
```bash
uv sync
```

3. Configure ClickHouse connection:
   - Edit `mcp-config.json` at `mcpServers.mcp-clickhouse.env`
   - Or set `CLICKHOUSE_*` environment variables for the MCP server

### Running the Example

```bash
uv run src/sql2text/example.py
```

This will:
1. Connect to the ClickHouse demo server
2. Run three demonstration examples:
   - Simple query analysis
   - Data exploration guide
   - Query optimization advice
3. Offer an interactive mode for custom queries

## MCP Server Configuration

The project includes a pre-configured MCP server setup for ClickHouse. Use the provided `mcp-config.json`:

```json
{
  "mcpServers": {
    "mcp-clickhouse": {
      "command": "uvx",
      "args": [
        "--python",
        "3.10",
        "mcp-clickhouse"
      ],
      "env": {
        "CLICKHOUSE_HOST": "sql-clickhouse.clickhouse.com",
        "CLICKHOUSE_PORT": "8443",
        "CLICKHOUSE_USER": "demo",
        "CLICKHOUSE_PASSWORD": "",
        "CLICKHOUSE_SECURE": "true",
        "CLICKHOUSE_VERIFY": "true",
        "CLICKHOUSE_CONNECT_TIMEOUT": "30",
        "CLICKHOUSE_SEND_RECEIVE_TIMEOUT": "30"
      }
    }
  }
}
```

### Linkup Remote MCP

You can also use the Linkup hosted MCP endpoint. Add this entry to `mcp-config.json`:

```json
{
  "mcpServers": {
    "linkup": {
      "url": "https://mcp.linkup.so/sse?apiKey={LINKUP_API_KEY}"
    }
  }
}
```

Alternatively, set `LINKUP_API_KEY` in your environment, and the example will construct the URL automatically. For details, see the Linkup documentation: [Remote MCP](https://docs.linkup.so/pages/integrations/mcp/mcp#remote-mcp).

Run the standalone Linkup example:

```bash
uv run src/sql2text/example_linkup.py
```

## Usage Examples

### 1. SQL Query Analysis

```python
from sql2text.example import sql_analyzer_agent, Runner

query = "SELECT COUNT(*) as total_users FROM system.users"
result = await Runner.run(
    sql_analyzer_agent,
    input=f"Analyze this query: {query}"
)
print(result.final_output)
```

### 2. Data Exploration

```python
from sql2text.example import data_explorer_agent, Runner

result = await Runner.run(
    data_explorer_agent,
    input="Help me explore the available tables in my ClickHouse database"
)
print(result.final_output)
```

### 3. Query Optimization

```python
from sql2text.example import query_optimizer_agent, Runner

complex_query = """
SELECT database, table, COUNT(*) as column_count
FROM system.columns 
WHERE database != 'system'
GROUP BY database, table
ORDER BY column_count DESC
LIMIT 10
"""

result = await Runner.run(
    query_optimizer_agent,
    input=f"Optimize this query: {complex_query}"
)
print(result.final_output)
```

### 4. Simple Weather Agent (Linkup + OpenAI)

This minimal agent uses OpenAI tool-calling with Linkup search to answer weather questions.

Prerequisites:

```bash
uv add openai linkup-sdk
export OPENAI_API_KEY=your-openai-key
export LINKUP_API_KEY=your-linkup-key
```

Run:

```bash
uv run src/sql2text/agent_weather.py "San Francisco"
```

Reference: [Linkup + OpenAI](https://docs.linkup.so/pages/integrations/linkup-openai)

### 5. Generalized Research Agent (Linkup + DeepL)

Searches the web via Linkup, synthesizes a cited answer, and can translate sources or final output via DeepL.

```bash
export OPENAI_API_KEY=your-openai-key
export LINKUP_API_KEY=your-linkup-key
export DEEPL_AUTH_KEY=your-deepl-key   # optional for translation

uv run src/sql2text/agent_research.py "Impact of LLMs on education" \
  --depth standard \
  --source-translation-lang DE \
  --output-translation-lang FR

Interactive chat mode:

```bash
uv run src/sql2text/agent_research.py --chat
# Commands inside chat:
#   /depth standard|deep
#   /srclang CODE
#   /outlang CODE
#   /quit
```
```

## Architecture

The project uses a multi-agent system with specialized roles:

- **SQL Analyzer Agent**: Explains what SQL queries do in business terms
- **Data Explorer Agent**: Helps users understand their data structure and content
- **Query Optimizer Agent**: Provides ClickHouse-specific performance recommendations
- **SQL2Text Coordinator**: Routes requests to appropriate specialist agents

## Configuration

### MCP Server Configuration (config-first)

The ClickHouse connection is configured through the MCP server. Prefer using the provided `mcp-config.json` or `CLICKHOUSE_*` environment variables:

**Option 1: Use the provided `mcp-config.json`**
```json
{
  "mcpServers": {
    "mcp-clickhouse": {
      "env": {
        "CLICKHOUSE_HOST": "your-clickhouse-host",
        "CLICKHOUSE_PORT": "8443",
        "CLICKHOUSE_USER": "your-username",
        "CLICKHOUSE_PASSWORD": "your-password"
      }
    }
  }
}
```

You can also configure the ClickHouse Remote MCP server directly with a URL (OAuth handled by the client):

```json
{
  "mcpServers": {
    "clickhouse-remote": {
      "url": "https://mcp.clickhouse.cloud/mcp"
    }
  }
}
```

**Option 2: Use environment variables (override config at runtime)**
```bash
export CLICKHOUSE_HOST=your-clickhouse-host
export CLICKHOUSE_PORT=8443
export CLICKHOUSE_USER=your-username
export CLICKHOUSE_PASSWORD=your-password
export CLICKHOUSE_SECURE=true
export CLICKHOUSE_VERIFY=true
# Or target the remote MCP explicitly
export MCP_URL=https://mcp.clickhouse.cloud/mcp
```

See the ClickHouse guide for enabling and using the Remote MCP server: [ClickHouse Cloud Remote MCP](`https://clickhouse.com/docs/use-cases/AI/MCP/remote_mcp`).

## Interactive Mode

The example includes an interactive mode where you can:

- Ask questions about SQL queries
- Request data exploration help
- Get optimization advice
- Explore your ClickHouse database interactively

Run with interactive mode:
```bash
uv run src/sql2text/example.py
# Choose 'y' when prompted for interactive mode
```

## Dependencies

- `openai-agents`: AI agent framework
- `mcp`: Model Context Protocol support

**Note**: ClickHouse connectivity is handled by the MCP server, which is run on-demand using `uvx`. No server installation is required - `uvx` automatically downloads and runs the MCP server when needed.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions or issues:
- Open an issue on GitHub
- Check the ClickHouse documentation
- Review the MCP protocol documentation
