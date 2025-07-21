#!/bin/bash
# Quick start script for Jupyter MCP Server
# This starts the services without running the full demo

set -e

echo "🪐✨ Starting Jupyter MCP Server..."
echo "=================================="

# Stop any existing services
echo "🛑 Stopping any existing services..."
docker-compose down

# Start services
echo "🚀 Starting services..."
docker-compose up -d --build

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

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
echo "🛠️  Management Commands:"
echo "• Stop services: docker-compose down"
echo "• View logs: docker-compose logs -f"
echo "• Run full demo: python test_mcp_demo.py"
echo ""
echo "Happy coding! 🚀" 