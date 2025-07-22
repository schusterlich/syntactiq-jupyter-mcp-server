# Copyright (c) 2023-2024 Datalayer, Inc.
#
# BSD 3-Clause License

"""
Custom API routes for Jupyter MCP Server.

This module contains all the custom HTTP endpoints that provide
administrative and health check functionality for the MCP server.
"""

import logging
from fastapi import Request
from starlette.responses import JSONResponse
from mcp.server import FastMCP

from jupyter_mcp_server.models import RoomRuntime
import jupyter_mcp_server.config as config
from jupyter_mcp_server.server import kernel, __start_kernel, __start_notebook_connection

logger = logging.getLogger(__name__)


def register_routes(mcp_server: FastMCP):
    """Register all custom routes with the provided FastMCP server instance."""
    
    # Administrative routes
    mcp_server.custom_route("/api/connect", ["PUT"])(connect)
    mcp_server.custom_route("/api/stop", ["DELETE"])(stop)
    
    # Health check route
    mcp_server.custom_route("/api/healthz", ["GET"])(health_check)


async def connect(request: Request):
    """Connect to a room and a runtime from the Jupyter MCP server."""

    data = await request.json()
    logger.info("Connecting to room_runtime:", data)

    room_runtime = RoomRuntime(**data)

    global kernel
    if kernel:
        try:
            kernel.stop()
        except Exception as e:
            logger.warning(f"Error stopping kernel during connect: {e}")

    # Update configuration
    config.PROVIDER = room_runtime.provider
    config.RUNTIME_URL = room_runtime.runtime_url
    config.RUNTIME_ID = room_runtime.runtime_id
    config.RUNTIME_TOKEN = room_runtime.runtime_token
    config.ROOM_URL = room_runtime.room_url
    config.ROOM_ID = room_runtime.room_id
    config.ROOM_TOKEN = room_runtime.room_token

    try:
        __start_kernel()
        await __start_notebook_connection()
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def stop(request: Request):
    global kernel
    try:
        if kernel:
            await kernel.stop()
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error(f"Error stopping kernel: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def health_check(request: Request):
    """Custom health check endpoint"""
    kernel_status = "unknown"
    try:
        if kernel:
            kernel_status = "alive" if hasattr(kernel, 'is_alive') and kernel.is_alive() else "dead"
        else:
            kernel_status = "not_initialized"
    except Exception:
        kernel_status = "error"
    return JSONResponse(
        {
            "success": True,
            "service": "jupyter-mcp-server",
            "message": "Jupyter MCP Server is running.",
            "status": "healthy",
            "kernel_status": kernel_status,
        }
    )