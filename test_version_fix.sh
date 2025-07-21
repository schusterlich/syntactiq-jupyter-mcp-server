#!/bin/bash

# Test script for version compatibility fix
# This script tests the custom MCP server build with aligned package versions

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Testing Jupyter MCP Server Version Compatibility Fix${NC}"
echo "============================================================"

# Step 1: Stop any existing containers
echo -e "${YELLOW}🛑 Stopping existing containers...${NC}"
docker-compose down 2>/dev/null || true

# Step 2: Build custom MCP server image
echo -e "${YELLOW}🔨 Building custom MCP server image...${NC}"
if docker-compose build jupyter-mcp-server; then
    echo -e "${GREEN}✅ Custom MCP server image built successfully${NC}"
else
    echo -e "${RED}❌ Failed to build custom MCP server image${NC}"
    exit 1
fi

# Step 3: Start services
echo -e "${YELLOW}🚀 Starting services with custom build...${NC}"
if docker-compose up -d; then
    echo -e "${GREEN}✅ Services started${NC}"
else
    echo -e "${RED}❌ Failed to start services${NC}"
    exit 1
fi

# Step 4: Wait for services to be healthy
echo -e "${YELLOW}⏳ Waiting for services to become healthy...${NC}"
for i in {1..24}; do  # Wait up to 2 minutes
    if docker-compose ps | grep -q "healthy"; then
        break
    fi
    echo -e "   Attempt $i/24..."
    sleep 5
done

# Step 5: Check JupyterLab health
echo -e "${YELLOW}🔍 Checking JupyterLab health...${NC}"
if curl -s "http://localhost:8888/api?token=MY_TOKEN" > /dev/null; then
    echo -e "${GREEN}✅ JupyterLab is responding${NC}"
else
    echo -e "${RED}❌ JupyterLab not responding${NC}"
    docker-compose logs jupyterlab | tail -10
    exit 1
fi

# Step 6: Check MCP Server health
echo -e "${YELLOW}🔍 Checking MCP Server health...${NC}"
if curl -s "http://localhost:4040/api/healthz" > /dev/null; then
    echo -e "${GREEN}✅ MCP Server is responding${NC}"
else
    echo -e "${RED}❌ MCP Server not responding${NC}"
    docker-compose logs jupyter-mcp-server | tail -10
    exit 1
fi

# Step 7: Check collaboration API availability
echo -e "${YELLOW}🔍 Checking collaboration API...${NC}"
COLLAB_RESPONSE=$(curl -s "http://localhost:8888/api/collaboration/room?token=MY_TOKEN" || echo "ERROR")
if [[ "$COLLAB_RESPONSE" != *"404"* ]] && [[ "$COLLAB_RESPONSE" != "ERROR" ]]; then
    echo -e "${GREEN}✅ Collaboration API is available${NC}"
else
    echo -e "${RED}❌ Collaboration API returning 404 - checking logs...${NC}"
    docker-compose logs jupyterlab | grep -E "(collaboration|ydoc|extension)" | tail -5
fi

# Step 8: Check package versions in MCP server
echo -e "${YELLOW}🔍 Checking package versions in MCP server...${NC}"
echo "Jupyter packages in MCP server:"
docker exec jupyter-mcp-server pip list | grep -E "(jupyter|pycrdt|datalayer)" | sort

echo -e "\n${YELLOW}🔍 Checking package versions in JupyterLab...${NC}"
echo "Jupyter packages in JupyterLab:"
docker exec jupyter-mcp-jupyterlab pip list | grep -E "(jupyter|pycrdt|datalayer)" | sort

# Step 9: Test MCP tool call
echo -e "\n${YELLOW}🔍 Testing MCP tool call...${NC}"
MCP_RESPONSE=$(curl -s -X POST "http://localhost:4040/mcp" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_notebook_info",
            "arguments": {}
        }
    }' || echo "ERROR")

if [[ "$MCP_RESPONSE" != "ERROR" ]] && [[ "$MCP_RESPONSE" == *"data:"* ]]; then
    echo -e "${GREEN}✅ MCP tool call successful${NC}"
    echo "Response preview: $(echo "$MCP_RESPONSE" | head -3)"
else
    echo -e "${RED}❌ MCP tool call failed${NC}"
    echo "Response: $MCP_RESPONSE"
fi

echo -e "\n${GREEN}🎉 Version compatibility test completed!${NC}"
echo "============================================================"
echo -e "${BLUE}💡 Next steps:${NC}"
echo "1. Open JupyterLab: http://localhost:8888?token=MY_TOKEN"
echo "2. Create/open notebook.ipynb"
echo "3. Run: python test_mcp_demo.py"
echo ""
echo -e "${YELLOW}To stop services: docker-compose down${NC}" 