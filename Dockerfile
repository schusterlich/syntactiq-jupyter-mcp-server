# Custom Jupyter MCP Server Docker Image
# Based on datalayer/jupyter-mcp-server but with version-aligned dependencies
# Copyright (c) 2023-2024 Datalayer, Inc.
# BSD 3-Clause License

FROM python:3.10-slim

WORKDIR /app

# Copy the MCP server source code (assuming we clone it)
COPY pyproject.toml pyproject.toml
COPY LICENSE LICENSE
COPY README.md README.md
COPY jupyter_mcp_server/ jupyter_mcp_server/

# Install the MCP server
RUN pip install -e .

# Align package versions to match our JupyterLab setup
# This ensures compatibility with jupyter_server_ydoc 2.1.0
RUN pip install --force-reinstall \
    jupyterlab==4.4.1 \
    jupyter-collaboration==4.0.2 \
    jupyter-server-ydoc==2.1.0 \
    ipykernel

# Handle pycrdt compatibility the same way as our JupyterLab container
RUN pip uninstall -y pycrdt datalayer_pycrdt || true
RUN pip install datalayer_pycrdt==0.12.17

# Ensure we have the exact same jupyter-nbmodel-client version that's compatible
RUN pip install --force-reinstall jupyter-nbmodel-client==0.13.5

EXPOSE 4040

ENTRYPOINT ["python", "-m", "jupyter_mcp_server"] 