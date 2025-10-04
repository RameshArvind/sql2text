import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import List, Optional

from mcp import ClientSession


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


def _load_linkup_url(config_path: Optional[str] = None) -> Optional[str]:
    """Resolve the Linkup Remote MCP URL.

    Order of precedence:
    1) MCP_URL env var (if explicitly set to the Linkup endpoint)
    2) mcp-config.json -> mcpServers["linkup"].url
    3) LINKUP_API_KEY env var -> constructs https://mcp.linkup.so/sse?apiKey=...
    """
    # Highest precedence: explicit env var
    url_env = os.environ.get("MCP_URL")
    if url_env and url_env.strip():
        return url_env

    path = _find_mcp_config_path(config_path or os.environ.get("MCP_CONFIG_PATH"))
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            servers = cfg.get("mcpServers", {})
            server_cfg = servers.get("linkup", {})
            url = server_cfg.get("url")
            if isinstance(url, str) and url.strip():
                return url
        except Exception:
            pass

    api_key = os.environ.get("LINKUP_API_KEY")
    if api_key:
        return f"https://mcp.linkup.so/sse?apiKey={api_key}"

    return None


async def demonstrate_linkup_remote_mcp() -> None:
    """Connect to Linkup Remote MCP (SSE) and run a sample `search` query.

    See docs: https://docs.linkup.so/pages/integrations/mcp/mcp#remote-mcp
    """
    # Optional CLI argument for custom query
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--query", type=str, default=None)
    args, _ = parser.parse_known_args()
    user_query = (
        args.query
        or "Latest updates about the Model Context Protocol; include 3 citations."
    )
    url = _load_linkup_url()
    if not url:
        print(
            "ℹ️ Linkup Remote MCP not configured. Set `mcpServers.linkup.url` in mcp-config.json "
            "or export LINKUP_API_KEY. See: https://docs.linkup.so/pages/integrations/mcp/mcp#remote-mcp"
        )
        return

    try:
        from mcp.client.sse import sse_client  # type: ignore

        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                print("✅ Connected to Linkup Remote MCP (SSE)")

                # Try to discover available tools
                tool_names: List[str] = []
                try:
                    tools = await session.list_tools()  # type: ignore
                    tool_names = [getattr(t, "name", "") for t in tools]
                except Exception:
                    tool_names = []

                if tool_names:
                    print(
                        "🧰 Available tools:",
                        ", ".join(sorted([t for t in tool_names if t])),
                    )
                else:
                    print("ℹ️ Could not list tools from server (continuing)...")

                # Prefer a tool with 'search' in the name
                selected_tool = None
                for name in tool_names:
                    if isinstance(name, str) and "search" in name.lower():
                        selected_tool = name
                        break

                if not selected_tool:
                    selected_tool = "search"  # best-guess fallback

                # Try multiple payload shapes
                payload_candidates = [
                    {"query": user_query},
                    {"q": user_query},
                    {"input": user_query},
                    {"text": user_query},
                ]

                last_error: Optional[Exception] = None
                for payload in payload_candidates:
                    try:
                        result = await session.call_tool(selected_tool, payload)  # type: ignore
                        preview = (
                            result.content[0].text[:500]
                            if result.content
                            else "<no content>"
                        )
                        print("\n🔎 Linkup Search result (preview):\n" + preview)
                        last_error = None
                        break
                    except Exception as e:
                        last_error = e

                if last_error:
                    print(
                        "⚠️ Could not invoke a search tool on Linkup MCP. "
                        "Available tools: "
                        + (", ".join(tool_names) if tool_names else "<unknown>")
                        + f". Last error: {last_error}"
                    )
    except Exception as e:
        print(f"❌ Failed to connect to Linkup Remote MCP: {e}")


async def main() -> None:
    await demonstrate_linkup_remote_mcp()


if __name__ == "__main__":
    asyncio.run(main())
