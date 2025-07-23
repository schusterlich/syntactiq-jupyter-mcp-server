#!/bin/bash

# ==============================================================================
# Syntactiq Jupyter MCP Server - Quick Start Script
# ==============================================================================

set -e

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Load environment configuration
if [ -f ".env" ]; then
    source .env
    echo -e "${GREEN}✓${NC} Loaded configuration from .env"
else
    echo -e "${YELLOW}⚠${NC} .env not found, using defaults"
    JUPYTER_TOKEN=${JUPYTER_TOKEN:-"MY_TOKEN"}
    JUPYTER_EXTERNAL_URL=${JUPYTER_EXTERNAL_URL:-"http://localhost:8888"}
fi

echo -e "${BLUE}🚀 Starting Syntactiq Jupyter MCP Server...${NC}"
echo ""

# Stop any existing containers
echo -e "${YELLOW}🛑 Stopping existing containers...${NC}"
docker-compose down --remove-orphans 2>/dev/null || true

# Build and start services
echo -e "${CYAN}🔨 Building and starting services...${NC}"
docker-compose up -d --build

# Wait for services to be healthy
echo -e "${PURPLE}⏱️  Waiting for services to be ready...${NC}"

# Wait for JupyterLab
echo -n "• JupyterLab: "
while ! curl -s "${JUPYTER_EXTERNAL_URL}/api/kernelspecs?token=${JUPYTER_TOKEN}" > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
echo -e " ${GREEN}✓${NC}"

# Wait for MCP Server  
echo -n "• MCP Server: "
while ! curl -s "http://localhost:4040/api/healthz" > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
echo -e " ${GREEN}✓${NC}"

echo ""
echo -e "${GREEN}🎉 All services are ready!${NC}"
echo ""
echo -e "${CYAN}📋 Access Information:${NC}"
echo -e "• JupyterLab: ${JUPYTER_EXTERNAL_URL}?token=${JUPYTER_TOKEN}"
echo -e "• MCP Server: http://localhost:4040"
echo ""
echo -e "${YELLOW}💡 Quick Commands:${NC}"
echo -e "• View logs: ${BLUE}docker-compose logs -f${NC}"
echo -e "• Stop services: ${BLUE}docker-compose down${NC}"
echo -e "• Run tests: ${BLUE}python test_suites/mcp_test_suite.py${NC}"
echo "" 