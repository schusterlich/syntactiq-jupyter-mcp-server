#!/bin/bash
# Jupyter MCP Server with Iframe Switching - Quick Start
# Enhanced startup script for the final iframe + MCP integration

set -e

echo "🪐✨ Starting Jupyter MCP Server with Iframe Switching..."
echo "========================================================="

# Stop any existing services
echo "🛑 Stopping any existing services..."
docker-compose down

# Start services
echo "🚀 Starting services..."
docker-compose up -d --build

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 15

# Check health
echo "🔍 Checking service health..."

# Check Jupyter
if curl -s -f "http://localhost:8888/api" > /dev/null; then
    echo "✅ JupyterLab is running"
else
    echo "❌ JupyterLab is not responding"
fi

# Check MCP Server
if curl -s -f "http://localhost:4040/api/healthz" > /dev/null; then
    echo "✅ MCP Server is running"
else
    echo "❌ MCP Server is not responding"
fi

echo ""
echo "🎉 Services are ready!"
echo "======================"
echo ""
echo "📋 Access Information:"
echo "• JupyterLab: http://localhost:8888?token=MY_TOKEN"
echo "• MCP Server: http://localhost:4040"
echo "• Health Check: http://localhost:4040/api/healthz"
echo ""
echo "🧪 Testing Iframe Switching:"
echo "1. Start HTTP server: python3 -m http.server 8080 --bind 127.0.0.1 &"
echo "2. Open test page: http://localhost:8080/interactive_mcp_test.html"
echo "3. Try notebook switching and MCP operations!"
echo ""
echo "🛠️  Management Commands:"
echo "• Stop services: docker-compose down"
echo "• View logs: docker-compose logs -f"
echo "• Test MCP: python mcp_test_suite.py"
echo ""
echo "🎯 What to test:"
echo "• Switch between Analysis 1/2 notebooks"
echo "• Watch MCP Server Target update"
echo "• Add markdown/code cells"
echo "• Execute code and see results"
echo ""
echo "Happy coding! 🚀" 