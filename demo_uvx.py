#!/usr/bin/env python3
"""
Demo script showing how uvx runs MCP servers on-demand.
This script demonstrates the zero-installation approach.
"""

import asyncio
import os
import subprocess
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def check_uvx():
    """Check if uvx is available."""
    try:
        result = subprocess.run(["uvx", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ uvx is available: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ uvx check failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ uvx not found. Please install uv (which includes uvx):")
        print("   curl -LsSf https://astral.sh/uv/install.sh | sh")
        return False


async def demo_mcp_with_uvx():
    """Demonstrate MCP server running with uvx."""
    print("\n🚀 Demo: Running MCP ClickHouse server with uvx")
    print("=" * 60)

    try:
        from sql2text.example import MCPClickHouseClient

        print("📦 Creating MCP client...")
        client = MCPClickHouseClient()

        print(
            "🔗 Connecting to ClickHouse via MCP (uvx will download mcp-clickhouse)..."
        )
        print("   This may take a moment on first run as uvx downloads the package...")

        await client.connect()

        print("\n🎉 Success! MCP server is running via uvx")
        print("   No permanent installation required!")

        # Try a simple query
        print("\n📊 Testing with a simple query...")
        try:
            result = await client.execute_query("SELECT 1 as test_value")
            print(f"   Query result: {result}")
        except Exception as e:
            print(f"   Query test failed: {e}")

        print("\n✨ Demo completed successfully!")
        print("   The MCP server was downloaded and run on-demand by uvx")

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure uvx is available")
        print("2. Check internet connection (uvx needs to download mcp-clickhouse)")
        print("3. Verify ClickHouse server accessibility")


def main():
    """Run the uvx demo."""
    print("🧪 uvx MCP Server Demo")
    print("=" * 30)

    # Check uvx availability
    if not check_uvx():
        return False

    # Run the demo
    asyncio.run(demo_mcp_with_uvx())
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
