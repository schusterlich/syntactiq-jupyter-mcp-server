# Copyright (c) 2023-2024 Datalayer, Inc.
#
# BSD 3-Clause License

"""
Global configuration variables for Jupyter MCP Server.
"""

import os

###############################################################################
# Transport & Provider Configuration
###############################################################################

TRANSPORT: str = os.getenv("TRANSPORT", "stdio")
PROVIDER: str = os.getenv("PROVIDER", "jupyter")

###############################################################################
# Runtime Configuration
###############################################################################

RUNTIME_URL: str = os.getenv("RUNTIME_URL", "http://localhost:8888")
START_NEW_RUNTIME: bool = os.getenv("START_NEW_RUNTIME", "false").lower() == "true"
RUNTIME_ID: str | None = os.getenv("RUNTIME_ID")
RUNTIME_TOKEN: str | None = os.getenv("RUNTIME_TOKEN")

###############################################################################
# Room Configuration  
###############################################################################

ROOM_URL: str = os.getenv("ROOM_URL", "http://localhost:8888")
ROOM_ID: str = os.getenv("ROOM_ID", "notebook.ipynb")
ROOM_TOKEN: str | None = os.getenv("ROOM_TOKEN")
 