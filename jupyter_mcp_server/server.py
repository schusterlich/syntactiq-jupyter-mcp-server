# Copyright (c) 2023-2024 Datalayer, Inc.
#
# BSD 3-Clause License
#
# Heavily Modified by syntactiq.ai

import asyncio
import logging
import time
from datetime import datetime
from typing import Union, Dict, Any
from concurrent.futures import ThreadPoolExecutor

import click
import httpx
import uvicorn
# Note: Request import moved to routes.py
from jupyter_kernel_client import KernelClient
from jupyter_nbmodel_client import (
    NbModelClient,
    get_notebook_websocket_url,
)
from mcp.server import FastMCP
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

from jupyter_mcp_server import config
from jupyter_mcp_server.config import (
    TRANSPORT, PROVIDER, RUNTIME_URL, START_NEW_RUNTIME, RUNTIME_ID, RUNTIME_TOKEN
)

# Global variables for kernel and notebook connection
kernel = None
notebook_connection = None

logger = logging.getLogger(__name__)

# Connection management functions merged from connections.py

def __start_kernel():
    """Start the Jupyter kernel with error handling."""
    global kernel
    try:
        if kernel:
            kernel.stop()
    except Exception as e:
        logger.warning(f"Error stopping existing kernel: {e}")
    
    try:
        # Initialize the kernel client with the provided parameters.
        kernel = KernelClient(server_url=config.RUNTIME_URL, token=config.RUNTIME_TOKEN, kernel_id=config.RUNTIME_ID)
        kernel.start()
        logger.info("Kernel started successfully")
    except Exception as e:
        logger.error(f"Failed to start kernel: {e}")
        kernel = None
        raise

async def __start_notebook_connection():
    """Establish a persistent connection to the notebook."""
    global notebook_connection
    try:
        if notebook_connection:
            logger.info("Stopping existing notebook connection...")
            await notebook_connection.stop()
    except Exception as e:
        logger.warning(f"Error stopping existing notebook connection: {e}")
    
    try:
        logger.info(f"Establishing notebook connection to {config.ROOM_URL} for {config.ROOM_ID}")
        # Initialize the persistent notebook connection using WebSocket URL
        websocket_url = get_notebook_websocket_url(
            server_url=config.ROOM_URL, 
            token=config.ROOM_TOKEN, 
            path=config.ROOM_ID, 
            provider=PROVIDER
        )
        logger.info(f"WebSocket URL: {websocket_url}")
        
        notebook_connection = NbModelClient(websocket_url)
        await notebook_connection.start()
        logger.info(f"Persistent notebook connection established for: {config.ROOM_ID}")
        
        # Verify the connection immediately
        if hasattr(notebook_connection, '_doc'):
            doc = notebook_connection._doc
            if doc is not None:
                logger.info(f"Document verified, has {len(doc._ycells) if hasattr(doc, '_ycells') else 'unknown'} cells")
            else:
                logger.error("Document is None after connection")
                notebook_connection = None
                raise Exception("Document is None after establishing connection")
        else:
            logger.error("Connection has no _doc attribute")
            notebook_connection = None
            raise Exception("Connection established but has no _doc attribute")
            
    except Exception as e:
        logger.error(f"Failed to start notebook connection: {e}")
        notebook_connection = None
        raise

async def __ensure_notebook_connection():
    """Ensure notebook connection is alive, restart if needed."""
    global notebook_connection
    
    if notebook_connection is None:
        logger.info("No notebook connection found, establishing new connection...")
        await __start_notebook_connection()
        
        # Verify that connection was actually established
        if notebook_connection is None:
            raise Exception("Failed to establish notebook connection - connection is still None")
        
        # Verify that connection has a valid document
        try:
            ydoc = notebook_connection._doc
            if ydoc is None:
                raise Exception("Connection established but document is None")
        except AttributeError:
            raise Exception("Connection established but has no _doc attribute")
        
        logger.info("Notebook connection verified and ready")
        return
    
    try:
        # Test if connection is still alive by accessing the document
        ydoc = notebook_connection._doc
        
        if ydoc is None:
            raise Exception("Document is None")
        
        # Test that document has cells attribute
        len(ydoc._ycells) if hasattr(ydoc, '_ycells') else 0
        
        # Connection seems alive
        logger.debug("Existing notebook connection verified as active")
        return
        
    except Exception as e:
        logger.warning(f"Notebook connection lost ({e}), re-establishing...")
        notebook_connection = None  # Reset to None before retrying
        await __start_notebook_connection()
        
        # Verify the new connection
        if notebook_connection is None:
            raise Exception("Failed to re-establish notebook connection - connection is still None")
        
        try:
            ydoc = notebook_connection._doc
            if ydoc is None:
                raise Exception("Re-established connection but document is None")
        except AttributeError:
            raise Exception("Re-established connection but has no _doc attribute")
        
        logger.info("Notebook connection re-established and verified")

async def __ensure_kernel_alive():
    """Ensure kernel is alive, restart if needed."""
    global kernel
    
    # Check if kernel exists and is alive
    if kernel and hasattr(kernel, 'is_alive') and kernel.is_alive():
        return
    
    logger.info("Kernel is None or not alive, starting new kernel")
    __start_kernel()

# Alternative approach: Create a custom execution function that forces updates
async def __execute_cell_and_wait_for_completion(notebook, cell_index, kernel, timeout_seconds=300) -> bool:
    """Execute cell and wait for actual completion with proper synchronization."""
    start_time = time.time()
    
    try:
        # Execute cell in thread and wait for actual completion
        execution_task = asyncio.create_task(
            asyncio.to_thread(notebook.execute_cell, cell_index, kernel)
        )
        
        # Wait for execution to complete with timeout
        await asyncio.wait_for(execution_task, timeout=timeout_seconds)
        
        # Execution completed successfully
        elapsed = time.time() - start_time
        logger.info(f"Cell {cell_index} execution completed successfully in {elapsed:.2f}s")
        return True
        
    except asyncio.TimeoutError:
        # Cancel execution and interrupt kernel
        execution_task.cancel()
        try:
            if hasattr(kernel, 'interrupt'):
                kernel.interrupt()
                logger.info(f"Interrupted kernel after {timeout_seconds}s timeout")
        except Exception as interrupt_err:
            logger.warning(f"Failed to interrupt kernel: {interrupt_err}")
        
        elapsed = time.time() - start_time
        raise asyncio.TimeoutError(f"Cell {cell_index} execution timed out after {elapsed:.1f}s")
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Cell {cell_index} execution failed after {elapsed:.2f}s: {e}")
        raise

async def __wait_for_execution_outputs(notebook, cell_index: int, max_wait_seconds: int = 5) -> bool:
    """Wait for execution outputs to be available in the notebook after execution completes."""
    start_time = time.time()
    
    while time.time() - start_time < max_wait_seconds:
        try:
            ydoc = notebook._doc
            if cell_index < len(ydoc._ycells):
                cell = ydoc._ycells[cell_index]
                outputs = cell.get("outputs", [])
                
                # Check if outputs are available (even if empty, execution should set this)
                if outputs is not None:
                    return True
        except Exception:
            pass
        
        await asyncio.sleep(0.1)  # Brief polling for output availability
    
    # Even if no outputs, execution may have completed
    logger.warning(f"Outputs not immediately available for cell {cell_index}, proceeding anyway")
    return True

def __is_kernel_busy(kernel):
    """Check if kernel is currently executing something."""
    try:
        # This is a simple check - you might need to adapt based on your kernel client
        if hasattr(kernel, '_client') and hasattr(kernel._client, 'is_alive'):
            return kernel._client.is_alive()
        return False
    except Exception:
        return False

async def __wait_for_kernel_idle(kernel, max_wait_seconds=60):
    """Wait for kernel to become idle before proceeding."""
    start_time = time.time()
    while __is_kernel_busy(kernel):
        elapsed = time.time() - start_time
        if elapsed > max_wait_seconds:
            logger.warning(f"Kernel still busy after {max_wait_seconds}s, proceeding anyway")
            break
        logger.info(f"Waiting for kernel to become idle... ({elapsed:.1f}s)")
        await asyncio.sleep(1)

async def __safe_notebook_operation(operation_func, max_retries=3):
    """Safely execute notebook operations with connection recovery."""
    for attempt in range(max_retries):
        try:
            return await operation_func()
        except Exception as e:
            error_msg = str(e).lower()
            if any(err in error_msg for err in ["websocketclosederror", "connection is already closed", "connection closed"]):
                if attempt < max_retries - 1:
                    logger.warning(f"Connection lost, retrying... (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(1 + attempt)  # Increasing delay
                    continue
                else:
                    logger.error(f"Failed after {max_retries} attempts: {e}")
                    raise Exception(f"Connection failed after {max_retries} retries: {e}")
            else:
                # Non-connection error, don't retry
                raise e
    
    raise Exception("Unexpected error in retry logic")

async def __wait_for_cell_count_change(notebook, expected_count: int, max_wait_seconds: int = 10) -> bool:
    """Wait for notebook cell count to reach expected value with proper synchronization."""
    start_time = time.time()
    
    while time.time() - start_time < max_wait_seconds:
        try:
            ydoc = notebook._doc
            current_count = len(ydoc._ycells)
            if current_count == expected_count:
                return True
        except Exception:
            pass
        await asyncio.sleep(0.1)  # Brief polling interval
    
    return False

async def __wait_for_cell_content_change(notebook, cell_index: int, expected_content: str, max_wait_seconds: int = 10) -> bool:
    """Wait for specific cell content to be updated with proper synchronization."""
    start_time = time.time()
    expected_content = expected_content.strip()
    
    while time.time() - start_time < max_wait_seconds:
        try:
            ydoc = notebook._doc
            if cell_index < len(ydoc._ycells):
                cell = ydoc._ycells[cell_index]
                current_source = cell.get("source", "")
                if isinstance(current_source, list):
                    current_source = ''.join(current_source)
                current_source = str(current_source).strip()
                
                if expected_content in current_source:
                    return True
        except Exception:
            pass
        await asyncio.sleep(0.1)  # Brief polling interval
    
    return False

from jupyter_mcp_server.tools import register_tools
from jupyter_mcp_server.routes import register_routes

###############################################################################

class FastMCPWithCORS(FastMCP):
    def streamable_http_app(self) -> Starlette:
        """Return StreamableHTTP server app with CORS middleware
        See: https://github.com/modelcontextprotocol/python-sdk/issues/187
        """
        # Get the original Starlette app
        app = super().streamable_http_app()
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, should set specific domains
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )        
        return app
    
    def sse_app(self, mount_path: str | None = None) -> Starlette:
        """Return SSE server app with CORS middleware"""
        # Get the original Starlette app
        app = super().sse_app(mount_path)
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, should set specific domains
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )        
        return app

###############################################################################

mcp = FastMCPWithCORS(name="Jupyter MCP Server", json_response=False, stateless_http=True)

# Register all MCP tools and routes
register_tools(mcp)
register_routes(mcp)

@click.group()
def server():
    """Manages Jupyter MCP Server."""
    pass


@server.command("connect")
@click.option(
    "--provider",
    envvar="PROVIDER",
    type=click.Choice(["jupyter", "datalayer"]),
    default="jupyter",
    help="The provider to use for the room and runtime. Defaults to 'jupyter'.",
)
@click.option(
    "--runtime-url",
    envvar="RUNTIME_URL",
    type=click.STRING,
    default="http://localhost:8888",
    help="The runtime URL to use. For the jupyter provider, this is the Jupyter server URL. For the datalayer provider, this is the Datalayer runtime URL.",
)
@click.option(
    "--runtime-id",
    envvar="RUNTIME_ID",
    type=click.STRING,
    default=None,
    help="The kernel ID to use. If not provided, a new kernel should be started.",
)
@click.option(
    "--runtime-token",
    envvar="RUNTIME_TOKEN",
    type=click.STRING,
    default=None,
    help="The runtime token to use for authentication with the provider. If not provided, the provider should accept anonymous requests.",
)
@click.option(
    "--room-url",
    envvar="ROOM_URL",
    type=click.STRING,
    default="http://localhost:8888",
    help="The room URL to use. For the jupyter provider, this is the Jupyter server URL. For the datalayer provider, this is the Datalayer room URL.",
)
@click.option(
    "--room-id",
    envvar="ROOM_ID",
    type=click.STRING,
    default="notebook.ipynb",
    help="The room id to use. For the jupyter provider, this is the notebook path. For the datalayer provider, this is the notebook path.",
)
@click.option(
    "--room-token",
    envvar="ROOM_TOKEN",
    type=click.STRING,
    default=None,
    help="The room token to use for authentication with the provider. If not provided, the provider should accept anonymous requests.",
)
@click.option(
    "--jupyter-mcp-server-url",
    envvar="JUPYTER_MCP_SERVER_URL",
    type=click.STRING,
    default="http://localhost:4040",
    help="The URL of the Jupyter MCP Server to connect to. Defaults to 'http://localhost:4040'.",
)
def connect_command(
    jupyter_mcp_server_url: str,
    runtime_url: str,
    runtime_id: str,
    runtime_token: str,
    room_url: str,
    room_id: str,
    room_token: str,
    provider: str,
):
    """Command to connect a Jupyter MCP Server to a room and a runtime."""

    global PROVIDER
    PROVIDER = provider

    config.RUNTIME_URL = runtime_url
    config.RUNTIME_ID = runtime_id
    config.RUNTIME_TOKEN = runtime_token

    config.ROOM_URL = room_url
    config.ROOM_ID = room_id
    config.ROOM_TOKEN = room_token

    room_runtime = RoomRuntime(
        provider=PROVIDER,
        runtime_url=RUNTIME_URL,
        runtime_id=RUNTIME_ID,
        runtime_token=RUNTIME_TOKEN,
        room_url=config.ROOM_URL,
        room_id=config.ROOM_ID,
        room_token=config.ROOM_TOKEN,
    )

    r = httpx.put(
        f"{jupyter_mcp_server_url}/api/connect",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        content=room_runtime.model_dump_json(),
    )
    r.raise_for_status()


@server.command("stop")
@click.option(
    "--jupyter-mcp-server-url",
    envvar="JUPYTER_MCP_SERVER_URL",
    type=click.STRING,
    default="http://localhost:4040",
    help="The URL of the Jupyter MCP Server to stop. Defaults to 'http://localhost:4040'.",
)
def stop_command(jupyter_mcp_server_url: str):
    r = httpx.delete(
        f"{jupyter_mcp_server_url}/api/stop",
    )
    r.raise_for_status()


@server.command("start")
@click.option(
    "--transport",
    envvar="TRANSPORT",
    type=click.Choice(["stdio", "streamable-http"]),
    default="stdio",
    help="The transport to use for the MCP server. Defaults to 'stdio'.",
)
@click.option(
    "--provider",
    envvar="PROVIDER",
    type=click.Choice(["jupyter", "datalayer"]),
    default="jupyter",
    help="The provider to use for the room and runtime. Defaults to 'jupyter'.",
)
@click.option(
    "--runtime-url",
    envvar="RUNTIME_URL",
    type=click.STRING,
    default="http://localhost:8888",
    help="The runtime URL to use. For the jupyter provider, this is the Jupyter server URL. For the datalayer provider, this is the Datalayer runtime URL.",
)
@click.option(
    "--start-new-runtime",
    envvar="START_NEW_RUNTIME",
    type=click.BOOL,
    default=True,
    help="Start a new runtime or use an existing one.",
)
@click.option(
    "--runtime-id",
    envvar="RUNTIME_ID",
    type=click.STRING,
    default=None,
    help="The kernel ID to use. If not provided, a new kernel should be started.",
)
@click.option(
    "--runtime-token",
    envvar="RUNTIME_TOKEN",
    type=click.STRING,
    default=None,
    help="The runtime token to use for authentication with the provider. If not provided, the provider should accept anonymous requests.",
)
@click.option(
    "--room-url",
    envvar="ROOM_URL",
    type=click.STRING,
    default="http://localhost:8888",
    help="The room URL to use. For the jupyter provider, this is the Jupyter server URL. For the datalayer provider, this is the Datalayer room URL.",
)
@click.option(
    "--room-id",
    envvar="ROOM_ID",
    type=click.STRING,
    default="notebook.ipynb",
    help="The room id to use. For the jupyter provider, this is the notebook path. For the datalayer provider, this is the notebook path.",
)
@click.option(
    "--room-token",
    envvar="ROOM_TOKEN",
    type=click.STRING,
    default=None,
    help="The room token to use for authentication with the provider. If not provided, the provider should accept anonymous requests.",
)
@click.option(
    "--port",
    envvar="PORT",
    type=click.INT,
    default=4040,
    help="The port to use for the Streamable HTTP transport. Ignored for stdio transport.",
)
def start_command(
    transport: str,
    start_new_runtime: bool,
    runtime_url: str,
    runtime_id: str,
    runtime_token: str,
    room_url: str,
    room_id: str,
    room_token: str,
    port: int,
    provider: str,
):
    """Start the Jupyter MCP server with a transport."""

    global TRANSPORT
    TRANSPORT = transport

    global PROVIDER
    PROVIDER = provider

    config.RUNTIME_URL = runtime_url
    global START_NEW_RUNTIME
    START_NEW_RUNTIME = start_new_runtime
    config.RUNTIME_ID = runtime_id
    config.RUNTIME_TOKEN = runtime_token

    config.ROOM_URL = room_url
    config.ROOM_ID = room_id
    config.ROOM_TOKEN = room_token

    if START_NEW_RUNTIME or config.RUNTIME_ID:
        try:
            __start_kernel()
        except Exception as e:
            logger.error(f"Failed to start kernel on startup: {e}")

    logger.info(f"Starting Jupyter MCP Server with transport: {transport}")

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "streamable-http":
        # Don't initialize connection during startup - let tools establish it when needed
        # The asyncio.run() here was causing the connection to be destroyed when the event loop closed
        logger.info("HTTP transport ready - notebook connection will be established on first tool call")
        uvicorn.run(mcp.streamable_http_app, host="0.0.0.0", port=port)  # noqa: S104
    else:
        raise Exception("Transport should be `stdio` or `streamable-http`.")


# HTTP Server factory for Docker deployment
def create_mcp_app() -> FastMCP:
    """Create and return the MCP app for production ASGI deployment."""
    init_server()


###############################################################################
# Main.


if __name__ == "__main__":
    start_command()