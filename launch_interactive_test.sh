#!/bin/bash
# 🚀 Interactive MCP Test Launcher
# Starts containers and opens the interactive test interface in browser

set -e

echo "🚀 Interactive MCP Test Launcher"
echo "================================"

# Start the main services
echo "🐳 Starting Jupyter MCP services..."
./quick_start.sh

echo ""
echo "🌐 Starting HTTP server for test interface..."

# Kill any existing HTTP server on port 8080
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "🛑 Stopping existing HTTP server on port 8080..."
    pkill -f "python3 -m http.server 8080" || true
    sleep 2
fi

# Start HTTP server in background
echo "📡 Starting HTTP server on port 8080..."
python3 -m http.server 8080 --bind 127.0.0.1 &
HTTP_PID=$!

# Wait for HTTP server to start
sleep 3

# Check if HTTP server is running
if curl -s -f "http://localhost:8080" > /dev/null 2>&1; then
    echo "✅ HTTP server is running"
else
    echo "❌ HTTP server failed to start"
    exit 1
fi

echo ""
echo "🎉 All services ready!"
echo "====================="

# Open browser automatically
TEST_URL="http://localhost:8080/interactive_mcp_test.html"

echo "📱 Opening interactive test in browser..."
echo "🔗 URL: $TEST_URL"

# Cross-platform browser opening
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open "$TEST_URL"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    xdg-open "$TEST_URL" || sensible-browser "$TEST_URL" || firefox "$TEST_URL" || chromium "$TEST_URL"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    # Windows
    start "$TEST_URL"
else
    echo "⚠️  Could not auto-open browser. Please manually navigate to:"
    echo "   $TEST_URL"
fi

echo ""
echo "🎯 Interactive Test Interface Features:"
echo "• 📊 Notebook switching via iframe reloading"
echo "• 🎯 MCP server context synchronization"
echo "• 🔧 Real-time notebook manipulation"
echo "• ✨ Visual feedback for all operations"
echo ""
echo "🛠️  Management:"
echo "• Stop all services: docker-compose down"
echo "• Stop HTTP server: kill $HTTP_PID"
echo "• View logs: docker-compose logs -f"
echo ""
echo "Happy testing! 🎉"

# Keep HTTP server PID for cleanup
echo "HTTP_PID=$HTTP_PID" > .http_server.pid
echo "💡 HTTP server PID saved to .http_server.pid" 