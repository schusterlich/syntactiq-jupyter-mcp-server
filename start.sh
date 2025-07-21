#!/bin/bash

# Jupyter MCP Server Startup Script
# Copyright (c) 2023-2024 Datalayer, Inc.
# BSD 3-Clause License

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
JUPYTER_TOKEN=${JUPYTER_TOKEN:-"jupyter-mcp-token-$(date +%s)"}
ROOM_ID=${ROOM_ID:-"notebook.ipynb"}
MCP_VERSION=${MCP_VERSION:-"latest"}

echo -e "${GREEN}🪐✨ Starting Jupyter MCP Server${NC}"
echo "======================================"

# Check if docker-compose exists
if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker or docker-compose not found${NC}"
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Create notebooks directory if it doesn't exist
if [ ! -d "notebooks" ]; then
    echo -e "${YELLOW}📁 Creating notebooks directory${NC}"
    mkdir -p notebooks
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚙️  Creating .env file${NC}"
    cat > .env << EOF
JUPYTER_TOKEN=${JUPYTER_TOKEN}
PROVIDER=jupyter
ROOM_ID=${ROOM_ID}
MCP_VERSION=${MCP_VERSION}
EOF
    echo -e "${GREEN}✅ Created .env with token: ${JUPYTER_TOKEN}${NC}"
fi

# Create example notebook if notebooks directory is empty
if [ ! "$(ls -A notebooks)" ]; then
    echo -e "${YELLOW}📓 Creating example notebook${NC}"
    cat > "notebooks/${ROOM_ID}" << 'EOF'
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Welcome to Jupyter MCP Server\n",
    "\n",
    "This notebook is connected to the Jupyter MCP Server, enabling AI agents to interact with this environment in real-time.\n",
    "\n",
    "## Available Tools\n",
    "\n",
    "The MCP server provides tools for:\n",
    "- Reading and writing cells\n",
    "- Executing code with progress monitoring\n",
    "- Managing notebook structure\n",
    "- Real-time collaboration\n",
    "\n",
    "Try running the cell below to test the connection:"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import sys\n",
    "print(f\"Python version: {sys.version}\")\n",
    "print(\"✅ Jupyter MCP Server is ready!\")\n",
    "\n",
    "# This cell can be executed by AI agents using the MCP server\n",
    "import pandas as pd\n",
    "import numpy as np\n",
    "import matplotlib.pyplot as plt\n",
    "\n",
    "print(f\"📊 Data science libraries loaded:\")\n",
    "print(f\"- pandas: {pd.__version__}\")\n",
    "print(f\"- numpy: {np.__version__}\")\n",
    "print(f\"- matplotlib: {plt.matplotlib.__version__}\")"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.10.0"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
EOF
    echo -e "${GREEN}✅ Created example notebook: ${ROOM_ID}${NC}"
fi

# Start services
echo -e "${GREEN}🚀 Starting services...${NC}"

# Use docker compose (newer) or docker-compose (legacy)
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}❌ Neither 'docker compose' nor 'docker-compose' found${NC}"
    exit 1
fi

$COMPOSE_CMD up -d

echo -e "${GREEN}⏳ Waiting for services to start...${NC}"
sleep 10

# Health checks
echo -e "${YELLOW}🔍 Checking service health...${NC}"

# Check JupyterLab
if curl -s -f "http://localhost:8888/api" > /dev/null; then
    echo -e "${GREEN}✅ JupyterLab is running${NC}"
else
    echo -e "${RED}❌ JupyterLab is not responding${NC}"
fi

# Check MCP Server
if curl -s -f "http://localhost:4040/api/healthz" > /dev/null; then
    echo -e "${GREEN}✅ MCP Server is running${NC}"
else
    echo -e "${RED}❌ MCP Server is not responding${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Jupyter MCP Server is ready!${NC}"
echo "======================================"
echo -e "${YELLOW}📋 Access Information:${NC}"
echo "• JupyterLab: http://localhost:8888"
echo "• Token: ${JUPYTER_TOKEN}"
echo "• MCP Server: http://localhost:4040"
echo "• Health Check: http://localhost:4040/api/healthz"
echo ""
echo -e "${YELLOW}📖 Next Steps:${NC}"
echo "1. Open JupyterLab in your browser"
echo "2. Configure your MCP client to use: http://localhost:4040"
echo "3. Start building AI agents with Jupyter capabilities!"
echo ""
echo -e "${YELLOW}🛠️  Management Commands:${NC}"
echo "• Stop services: $COMPOSE_CMD down"
echo "• View logs: $COMPOSE_CMD logs -f"
echo "• Restart: $COMPOSE_CMD restart"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}" 