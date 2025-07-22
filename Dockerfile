# Jupyter MCP Server - Simplified Docker Image
# Copyright (c) 2023-2024 Datalayer, Inc.
# BSD 3-Clause License

FROM python:3.10-slim

WORKDIR /app

# Copy the MCP server source code
COPY pyproject.toml pyproject.toml
COPY LICENSE LICENSE
COPY README.md README.md
COPY jupyter_mcp_server/ jupyter_mcp_server/

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install the MCP server and basic requirements
RUN pip install -e .

# Default port
EXPOSE 4040

# Start the MCP server
CMD ["python", "-m", "jupyter_mcp_server"] 