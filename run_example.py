#!/usr/bin/env python3
"""
Simple script to run the SQL2Text ClickHouse example.
This script provides an easy way to execute the example without navigating to the src directory.
"""

import sys
import os
import asyncio

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from sql2text.example import main

if __name__ == "__main__":
    print("🚀 Starting SQL2Text with ClickHouse MCP Server")
    print("=" * 60)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure you have:")
        print("1. Installed dependencies: uv sync")
        print("2. Valid ClickHouse connection settings")
        print("3. Internet access to reach the demo ClickHouse server")
