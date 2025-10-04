#!/bin/bash

echo "🚀 Setting up SQL2Text with ClickHouse MCP Server"
echo "=================================================="

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ UV is not installed. Please install UV first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✅ UV is installed"

# Install dependencies
echo "📦 Installing dependencies..."
uv sync

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Check if uvx is available
echo "🔧 Checking uvx availability..."
if command -v uvx &> /dev/null; then
    echo "✅ uvx is available - MCP server will be run on-demand"
else
    echo "❌ uvx is not available"
    echo "   uvx comes with uv, make sure you have the latest version"
    echo "   Update uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# Run tests
echo "🧪 Running setup tests..."
python test_setup.py

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To run the example:"
echo "  python run_example.py"
echo "  or"
echo "  uv run src/sql2text/example.py"
echo ""
echo "To test the setup:"
echo "  python test_setup.py"
echo ""
echo "To see uvx in action:"
echo "  python demo_uvx.py"
