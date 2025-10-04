# SQL2Text Usage Guide

This guide shows you how to use the SQL2Text tool with ClickHouse MCP server.

## Quick Start

1. **Setup** (one-time):
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

2. **Run the example**:
   ```bash
   python run_example.py
   ```

## What the Example Does

The example demonstrates three main capabilities:

### 1. SQL Query Analysis
- Takes a SQL query and explains what it does in plain English
- Identifies tables, columns, and operations involved
- Explains business logic and purpose
- Highlights potential performance issues

### 2. Data Exploration
- Lists available tables in your ClickHouse database
- Explains what each table contains
- Suggests interesting queries you could run
- Provides insights about data relationships

### 3. Query Optimization
- Analyzes ClickHouse queries for performance
- Suggests ClickHouse-specific optimizations
- Identifies potential bottlenecks
- Recommends alternative approaches

## Interactive Mode

After running the demonstration, you can enter interactive mode to:

- Ask questions about specific SQL queries
- Request help with data exploration
- Get optimization advice for your queries
- Execute queries directly with `run: SELECT ...`

## Example Interactions

```
> What does this query do: SELECT COUNT(*) FROM system.tables
> Show me what tables are available
> How can I optimize this query: SELECT * FROM large_table WHERE date > '2023-01-01'
> Run: SELECT database, COUNT(*) as table_count FROM system.tables GROUP BY database
```

## Weather Agent (Linkup + OpenAI)

This example uses OpenAI function calling with Linkup to fetch live weather info.

Setup:

```bash
uv add openai linkup-sdk
export OPENAI_API_KEY=your-openai-key
export LINKUP_API_KEY=your-linkup-key
```

Run:

```bash
uv run src/sql2text/agent_weather.py "Seattle"
```

Docs: [Linkup + OpenAI](https://docs.linkup.so/pages/integrations/linkup-openai)

## Research Agent (Linkup + DeepL)

General-purpose research with optional translation of sources or final output.

```bash
export OPENAI_API_KEY=your-openai-key
export LINKUP_API_KEY=your-linkup-key
export DEEPL_AUTH_KEY=your-deepl-key   # optional

uv run src/sql2text/agent_research.py "LLM safety best practices" --depth deep \
  --source-translation-lang ES --output-translation-lang EN

Interactive chat mode:

```bash
uv run src/sql2text/agent_research.py --chat
```

Commands:
- /depth standard|deep
- /srclang CODE
- /outlang CODE
- /quit
```

## MCP Server Configuration

The tool can use either the packaged stdio MCP server or the Remote MCP URL:
- **Host**: sql-clickhouse.clickhouse.com
- **Port**: 8443
- **User**: demo
- **Security**: SSL enabled

To use your own ClickHouse server, update `mcp-config.json` or set environment variables:

```json
{
  "mcpServers": {
    "mcp-clickhouse": {
      "env": {
        "CLICKHOUSE_HOST": "your-host",
        "CLICKHOUSE_PORT": "8443",
        "CLICKHOUSE_USER": "your-user",
        "CLICKHOUSE_PASSWORD": "your-password",
        "CLICKHOUSE_SECURE": "true",
        "CLICKHOUSE_VERIFY": "true"
      }
    }
  }
}
```

Or via environment variables:
```bash
export CLICKHOUSE_HOST=your-host
export CLICKHOUSE_PORT=8443
export CLICKHOUSE_USER=your-user
export CLICKHOUSE_PASSWORD=your-password
export CLICKHOUSE_SECURE=true
export CLICKHOUSE_VERIFY=true
# Or remote MCP URL (OAuth handled by client)
export MCP_URL=https://mcp.clickhouse.cloud/mcp
```

### Linkup Remote MCP

Add this to `mcp-config.json` to use Linkup's hosted MCP endpoint:

```json
{
  "mcpServers": {
    "linkup": {
      "url": "https://mcp.linkup.so/sse?apiKey={LINKUP_API_KEY}"
    }
  }
}
```

Or set an environment variable and let the example construct the URL:

```bash
export LINKUP_API_KEY=your-linkup-api-key
```

Run the Linkup demo path in the example script:

```bash
uv run src/sql2text/example.py
```

If Linkup is configured, you'll see a connection to the Linkup SSE endpoint and a sample `search` tool invocation. See Linkup docs for details: [Remote MCP](https://docs.linkup.so/pages/integrations/mcp/mcp#remote-mcp).

Run the dedicated Linkup example directly:

```bash
uv run src/sql2text/example_linkup.py
```

For the ClickHouse Remote MCP workflow and OAuth flow, see: [ClickHouse Cloud Remote MCP](`https://clickhouse.com/docs/use-cases/AI/MCP/remote_mcp`).

## Troubleshooting

### Connection Issues
- Make sure you have internet access
- Check if the demo ClickHouse server is accessible
- Verify MCP server installation: `uv add mcp-clickhouse`

### Import Errors
- Run `uv sync` to install dependencies
- Check Python version (requires 3.13+)

### MCP Server Issues
- Ensure `uvx` is available (comes with `uv`)
- Check the MCP server configuration
- Verify ClickHouse credentials
- `uvx` will automatically download `mcp-clickhouse` when needed

## Advanced Usage

### Custom Agents
You can create custom agents for specific use cases:

```python
custom_agent = Agent(
    name="Custom Analyzer",
    instructions="Your custom instructions here..."
)
```

### Direct MCP Communication
You can use the MCP client directly:

```python
from sql2text.example import MCPClickHouseClient

client = MCPClickHouseClient()
await client.connect()
result = await client.execute_query("SELECT 1")
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Run `python test_setup.py` to diagnose issues
3. Review the ClickHouse MCP server documentation
4. Open an issue on GitHub
