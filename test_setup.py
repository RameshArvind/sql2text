#!/usr/bin/env python3
"""
Test script to verify the SQL2Text setup and dependencies.
"""

import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_imports():
    """Test if all required modules can be imported."""
    print("🔍 Testing imports...")

    try:
        import asyncio

        print("✅ asyncio imported successfully")
    except ImportError as e:
        print(f"❌ asyncio import failed: {e}")
        return False

    try:
        from agents import Agent, Runner

        print("✅ openai-agents imported successfully")
    except ImportError as e:
        print(f"❌ openai-agents import failed: {e}")
        print("   Run: uv sync")
        return False

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        print("✅ MCP client imported successfully")
    except ImportError as e:
        print(f"❌ MCP import failed: {e}")
        print("   Run: uv sync")
        return False

    return True


def test_mcp_connection():
    """Test MCP ClickHouse connection."""
    print("\n🔗 Testing MCP ClickHouse connection...")

    try:
        from sql2text.example import MCPClickHouseClient

        # Create MCP client instance
        client = MCPClickHouseClient()
        print("✅ MCPClickHouseClient created successfully")

        # Test connection (this will actually try to connect to MCP server)
        import asyncio

        async def test_conn():
            try:
                await client.connect()
                print("✅ MCP ClickHouse server connection successful")
                return True
            except Exception as e:
                print(f"❌ MCP ClickHouse server connection failed: {e}")
                print(
                    "   This might be expected if the MCP server is not properly configured"
                )
                print(
                    "   Make sure uvx is available and mcp-clickhouse can be downloaded"
                )
                print("   uvx will automatically download mcp-clickhouse when needed")
                return False

        return asyncio.run(test_conn())

    except Exception as e:
        print(f"❌ MCP test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 SQL2Text Setup Test")
    print("=" * 40)

    # Test imports
    imports_ok = test_imports()

    if not imports_ok:
        print("\n❌ Import test failed. Please install dependencies with: uv sync")
        return False

    # Test MCP connection
    mcp_ok = test_mcp_connection()

    print("\n" + "=" * 40)
    if imports_ok and mcp_ok:
        print("🎉 All tests passed! You're ready to run the example.")
        print("\nTo run the example:")
        print("  python run_example.py")
        print("  or")
        print("  uv run src/sql2text/example.py")
    else:
        print("⚠️  Some tests failed, but you can still try running the example.")
        print(
            "The MCP connection test might fail if the mcp-clickhouse server is not installed."
        )
        print("Install it with: uv add mcp-clickhouse")

    return imports_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
