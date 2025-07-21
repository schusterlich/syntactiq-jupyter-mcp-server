# Copyright (c) 2023-2024 Datalayer, Inc.
#
# BSD 3-Clause License

import asyncio
import logging
import time
from datetime import datetime
from typing import Union, Dict, Any
from concurrent.futures import ThreadPoolExecutor

import click
import httpx
import uvicorn
from fastapi import Request
from jupyter_kernel_client import KernelClient
from jupyter_nbmodel_client import (
    NbModelClient,
    get_notebook_websocket_url,
)
from mcp.server import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from jupyter_mcp_server.models import RoomRuntime
from jupyter_mcp_server.utils import extract_output, safe_extract_outputs


###############################################################################


logger = logging.getLogger(__name__)


###############################################################################


TRANSPORT: str = "stdio"
PROVIDER: str = "jupyter"

RUNTIME_URL: str = "http://localhost:8888"
START_NEW_RUNTIME: bool = False
RUNTIME_ID: str | None = None
RUNTIME_TOKEN: str | None = None

ROOM_URL: str = "http://localhost:8888"
ROOM_ID: str = "notebook.ipynb"
ROOM_TOKEN: str | None = None


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

kernel = None


###############################################################################


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
        kernel = KernelClient(server_url=RUNTIME_URL, token=RUNTIME_TOKEN, kernel_id=RUNTIME_ID)
        kernel.start()
        logger.info("Kernel started successfully")
    except Exception as e:
        logger.error(f"Failed to start kernel: {e}")
        kernel = None
        raise


def __ensure_kernel_alive():
    """Ensure kernel is running, restart if needed."""
    global kernel
    if kernel is None:
        logger.info("Kernel is None, starting new kernel")
        __start_kernel()
    elif not hasattr(kernel, 'is_alive') or not kernel.is_alive():
        logger.info("Kernel is not alive, restarting")
        __start_kernel()


async def __execute_cell_with_timeout(notebook, cell_index, kernel, timeout_seconds=300):
    """Execute a cell with timeout and real-time output sync."""
    start_time = time.time()
    
    def _execute_sync():
        return notebook.execute_cell(cell_index, kernel)
    
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_execute_sync)
        
        while not future.done():
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                future.cancel()
                raise asyncio.TimeoutError(f"Cell execution timed out after {timeout_seconds} seconds")
            
            await asyncio.sleep(2)
            try:
                # Try to force document sync using the correct method
                ydoc = notebook._doc
                if hasattr(ydoc, 'flush') and callable(ydoc.flush):
                    ydoc.flush()  # Flush pending changes
                elif hasattr(notebook, '_websocket') and notebook._websocket:
                    # Force a small update to trigger sync
                    pass  # The websocket should auto-sync
                
                if cell_index < len(ydoc._ycells):
                    outputs = ydoc._ycells[cell_index].get("outputs", [])
                    if outputs:
                        logger.info(f"Cell {cell_index} executing... ({elapsed:.1f}s) - {len(outputs)} outputs so far")
            except Exception as e:
                logger.debug(f"Sync attempt failed: {e}")
                pass
        
        result = future.result()
        return result
        
    finally:
        executor.shutdown(wait=False)


# Alternative approach: Create a custom execution function that forces updates
async def __execute_cell_with_forced_sync(notebook, cell_index, kernel, timeout_seconds=300):
    """Execute cell with forced real-time synchronization."""
    start_time = time.time()
    
    # Start execution
    execution_future = asyncio.create_task(
        asyncio.to_thread(notebook.execute_cell, cell_index, kernel)
    )
    
    last_output_count = 0
    
    while not execution_future.done():
        elapsed = time.time() - start_time
        
        if elapsed > timeout_seconds:
            execution_future.cancel()
            try:
                if hasattr(kernel, 'interrupt'):
                    kernel.interrupt()
            except Exception:
                pass
            raise asyncio.TimeoutError(f"Cell execution timed out after {timeout_seconds} seconds")
        
        # Check for new outputs and try to trigger sync
        try:
            ydoc = notebook._doc
            current_outputs = ydoc._ycells[cell_index].get("outputs", [])
            
            if len(current_outputs) > last_output_count:
                last_output_count = len(current_outputs)
                logger.info(f"Cell {cell_index} progress: {len(current_outputs)} outputs after {elapsed:.1f}s")
                
                # Try different sync methods
                try:
                    # Method 1: Force Y-doc update
                    if hasattr(ydoc, 'observe') and hasattr(ydoc, 'unobserve'):
                        # Trigger observers by making a tiny change
                        pass
                        
                    # Method 2: Force websocket message
                    if hasattr(notebook, '_websocket') and notebook._websocket:
                        # The websocket should automatically sync on changes
                        pass
                        
                except Exception as sync_error:
                    logger.debug(f"Sync method failed: {sync_error}")
                    
        except Exception as e:
            logger.debug(f"Output check failed: {e}")
        
        await asyncio.sleep(1)  # Check every second
    
    # Get final result
    try:
        await execution_future
    except asyncio.CancelledError:
        pass
    
    return None


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


###############################################################################
# Custom Routes.


@mcp.custom_route("/api/connect", ["PUT"])
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

    global PROVIDER
    PROVIDER = room_runtime.provider

    global RUNTIME_URL
    RUNTIME_URL = room_runtime.runtime_url
    global RUNTIME_ID
    RUNTIME_ID = room_runtime.runtime_id
    global RUNTIME_TOKEN
    RUNTIME_TOKEN = room_runtime.runtime_token

    global ROOM_URL
    ROOM_URL = room_runtime.room_url
    global ROOM_ID
    ROOM_ID = room_runtime.room_id
    global ROOM_TOKEN
    ROOM_TOKEN = room_runtime.room_token

    try:
        __start_kernel()
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@mcp.custom_route("/api/stop", ["DELETE"])
async def stop(request: Request):
    global kernel
    try:
        if kernel:
            await kernel.stop()
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error(f"Error stopping kernel: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@mcp.custom_route("/api/healthz", ["GET"])
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


###############################################################################
# Tools.


@mcp.tool()
async def append_markdown_cell(cell_source: str) -> str:
    """Append at the end of the notebook a markdown cell with the provided source.

    Args:
        cell_source: Markdown source

    Returns:
        str: Success message
    """
    async def _append_markdown():
        notebook = None
        try:
            notebook = NbModelClient(
                get_notebook_websocket_url(
                    server_url=ROOM_URL, token=ROOM_TOKEN, path=ROOM_ID, provider=PROVIDER
                )
            )
            await notebook.start()
            notebook.add_markdown_cell(cell_source)
            return "Jupyter Markdown cell added."
        finally:
            if notebook:
                try:
                    await notebook.stop()
                except Exception as e:
                    logger.warning(f"Error stopping notebook in append_markdown_cell: {e}")
    
    return await __safe_notebook_operation(_append_markdown)


@mcp.tool()
async def insert_markdown_cell(cell_index: int, cell_source: str) -> str:
    """Insert a markdown cell in a Jupyter notebook.

    Args:
        cell_index: Index of the cell to insert (0-based)
        cell_source: Markdown source

    Returns:
        str: Success message
    """
    async def _insert_markdown():
        notebook = None
        try:
            notebook = NbModelClient(
                get_notebook_websocket_url(
                    server_url=ROOM_URL, token=ROOM_TOKEN, path=ROOM_ID, provider=PROVIDER
                )
            )
            await notebook.start()
            notebook.insert_markdown_cell(cell_index, cell_source)
            return f"Jupyter Markdown cell {cell_index} inserted."
        finally:
            if notebook:
                try:
                    await notebook.stop()
                except Exception as e:
                    logger.warning(f"Error stopping notebook in insert_markdown_cell: {e}")
    
    return await __safe_notebook_operation(_insert_markdown)


@mcp.tool()
async def overwrite_cell_source(cell_index: int, cell_source: str) -> str:
    """Overwrite the source of an existing cell.
       Note this does not execute the modified cell by itself.

    Args:
        cell_index: Index of the cell to overwrite (0-based)
        cell_source: New cell source - must match existing cell type

    Returns:
        str: Success message
    """
    async def _overwrite_cell():
        notebook = None
        try:
            notebook = NbModelClient(
                get_notebook_websocket_url(
                    server_url=ROOM_URL, token=ROOM_TOKEN, path=ROOM_ID, provider=PROVIDER
                )
            )
            await notebook.start()
            notebook.set_cell_source(cell_index, cell_source)
            return f"Cell {cell_index} overwritten successfully - use execute_cell to execute it if code"
        finally:
            if notebook:
                try:
                    await notebook.stop()
                except Exception as e:
                    logger.warning(f"Error stopping notebook in overwrite_cell_source: {e}")
    
    return await __safe_notebook_operation(_overwrite_cell)


@mcp.tool()
async def append_execute_code_cell(cell_source: str) -> list[str]:
    """Append at the end of the notebook a code cell with the provided source and execute it.

    Args:
        cell_source: Code source

    Returns:
        list[str]: List of outputs from the executed cell
    """
    async def _append_execute():
        __ensure_kernel_alive()
        notebook = None
        try:
            notebook = NbModelClient(
                get_notebook_websocket_url(
                    server_url=ROOM_URL, token=ROOM_TOKEN, path=ROOM_ID, provider=PROVIDER
                )
            )
            await notebook.start()
            cell_index = notebook.add_code_cell(cell_source)
            notebook.execute_cell(cell_index, kernel)

            ydoc = notebook._doc
            outputs = ydoc._ycells[cell_index]["outputs"]
            return safe_extract_outputs(outputs)
        finally:
            if notebook:
                try:
                    await notebook.stop()
                except Exception as e:
                    logger.warning(f"Error stopping notebook in append_execute_code_cell: {e}")
    
    return await __safe_notebook_operation(_append_execute)


@mcp.tool()
async def insert_execute_code_cell(cell_index: int, cell_source: str) -> list[str]:
    """Insert and execute a code cell in a Jupyter notebook.

    Args:
        cell_index: Index of the cell to insert (0-based)
        cell_source: Code source

    Returns:
        list[str]: List of outputs from the executed cell
    """
    async def _insert_execute():
        __ensure_kernel_alive()
        notebook = None
        try:
            notebook = NbModelClient(
                get_notebook_websocket_url(
                    server_url=ROOM_URL, token=ROOM_TOKEN, path=ROOM_ID, provider=PROVIDER
                )
            )
            await notebook.start()
            notebook.insert_code_cell(cell_index, cell_source)
            notebook.execute_cell(cell_index, kernel)

            ydoc = notebook._doc
            outputs = ydoc._ycells[cell_index]["outputs"]
            return safe_extract_outputs(outputs)
        finally:
            if notebook:
                try:
                    await notebook.stop()
                except Exception as e:
                    logger.warning(f"Error stopping notebook in insert_execute_code_cell: {e}")
    
    return await __safe_notebook_operation(_insert_execute)


@mcp.tool()
async def execute_cell_with_progress(cell_index: int, timeout_seconds: int = 300) -> list[str]:
    """Execute a specific cell with timeout and progress monitoring.
    Args:
        cell_index: Index of the cell to execute (0-based)
        timeout_seconds: Maximum time to wait for execution (default: 300s)
    Returns:
        list[str]: List of outputs from the executed cell
    """
    async def _execute():
        __ensure_kernel_alive()
        await __wait_for_kernel_idle(kernel, max_wait_seconds=30)
        
        notebook = None
        try:
            notebook = NbModelClient(
                get_notebook_websocket_url(
                    server_url=ROOM_URL, token=ROOM_TOKEN, path=ROOM_ID, provider=PROVIDER
                )
            )
            await notebook.start()

            ydoc = notebook._doc

            if cell_index < 0 or cell_index >= len(ydoc._ycells):
                raise ValueError(
                    f"Cell index {cell_index} is out of range. Notebook has {len(ydoc._ycells)} cells."
                )

            logger.info(f"Starting execution of cell {cell_index} with {timeout_seconds}s timeout")
            
            # Use the corrected timeout function
            await __execute_cell_with_forced_sync(notebook, cell_index, kernel, timeout_seconds)

            # Get final outputs
            ydoc = notebook._doc
            outputs = ydoc._ycells[cell_index]["outputs"]
            result = safe_extract_outputs(outputs)
            
            logger.info(f"Cell {cell_index} completed successfully with {len(result)} outputs")
            return result
            
        except asyncio.TimeoutError as e:
            logger.error(f"Cell {cell_index} execution timed out: {e}")
            try:
                if kernel and hasattr(kernel, 'interrupt'):
                    kernel.interrupt()
                    logger.info("Sent interrupt signal to kernel")
            except Exception as interrupt_err:
                logger.error(f"Failed to interrupt kernel: {interrupt_err}")
            
            # Return partial outputs if available
            try:
                if notebook:
                    ydoc = notebook._doc
                    outputs = ydoc._ycells[cell_index].get("outputs", [])
                    partial_outputs = safe_extract_outputs(outputs)
                    partial_outputs.append(f"[TIMEOUT ERROR: Execution exceeded {timeout_seconds} seconds]")
                    return partial_outputs
            except Exception:
                pass
            
            return [f"[TIMEOUT ERROR: Cell execution exceeded {timeout_seconds} seconds and was interrupted]"]
            
        except Exception as e:
            logger.error(f"Error executing cell {cell_index}: {e}")
            raise
            
        finally:
            if notebook:
                try:
                    await notebook.stop()
                except Exception as e:
                    logger.warning(f"Error stopping notebook in execute_cell_with_progress: {e}")
    
    return await __safe_notebook_operation(_execute, max_retries=1)

# Simpler real-time monitoring without forced sync
@mcp.tool()
async def execute_cell_simple_timeout(cell_index: int, timeout_seconds: int = 300) -> list[str]:
    """Execute a cell with simple timeout (no forced real-time sync). To be used for short-running cells.
    This won't force real-time updates but will work reliably.
    """
    async def _execute():
        __ensure_kernel_alive()
        await __wait_for_kernel_idle(kernel, max_wait_seconds=30)
        
        notebook = None
        try:
            notebook = NbModelClient(
                get_notebook_websocket_url(
                    server_url=ROOM_URL, token=ROOM_TOKEN, path=ROOM_ID, provider=PROVIDER
                )
            )
            await notebook.start()

            ydoc = notebook._doc
            if cell_index < 0 or cell_index >= len(ydoc._ycells):
                raise ValueError(f"Cell index {cell_index} is out of range.")

            logger.info(f"Starting execution of cell {cell_index} with {timeout_seconds}s timeout")
            
            # Simple execution with timeout
            execution_task = asyncio.create_task(
                asyncio.to_thread(notebook.execute_cell, cell_index, kernel)
            )
            
            try:
                await asyncio.wait_for(execution_task, timeout=timeout_seconds)
            except asyncio.TimeoutError:
                execution_task.cancel()
                if kernel and hasattr(kernel, 'interrupt'):
                    kernel.interrupt()
                return [f"[TIMEOUT ERROR: Cell execution exceeded {timeout_seconds} seconds]"]

            # Get final outputs
            outputs = ydoc._ycells[cell_index]["outputs"]
            result = safe_extract_outputs(outputs)
            
            logger.info(f"Cell {cell_index} completed successfully")
            return result
            
        finally:
            if notebook:
                try:
                    await notebook.stop()
                except Exception as e:
                    logger.warning(f"Error stopping notebook: {e}")
    
    return await __safe_notebook_operation(_execute, max_retries=1)


@mcp.tool()
async def execute_cell_streaming(cell_index: int, timeout_seconds: int = 300, progress_interval: int = 5) -> list[str]:
    """Execute cell with streaming progress updates. To be used for long-running cells.
    Args:
        cell_index: Index of the cell to execute (0-based)
        timeout_seconds: Maximum time to wait for execution (default: 300s)  
        progress_interval: Seconds between progress updates (default: 5s)
    Returns:
        list[str]: List of outputs including progress updates
    """
    async def _execute_streaming():
        __ensure_kernel_alive()
        await __wait_for_kernel_idle(kernel, max_wait_seconds=30)
        
        notebook = None
        outputs_log = []
        
        try:
            notebook = NbModelClient(
                get_notebook_websocket_url(
                    server_url=ROOM_URL, token=ROOM_TOKEN, path=ROOM_ID, provider=PROVIDER
                )
            )
            await notebook.start()

            ydoc = notebook._doc
            if cell_index < 0 or cell_index >= len(ydoc._ycells):
                raise ValueError(f"Cell index {cell_index} is out of range.")

            # Start execution in background
            execution_task = asyncio.create_task(
                asyncio.to_thread(notebook.execute_cell, cell_index, kernel)
            )
            
            start_time = time.time()
            last_output_count = 0
            
            # Monitor progress
            while not execution_task.done():
                elapsed = time.time() - start_time
                
                # Check timeout
                if elapsed > timeout_seconds:
                    execution_task.cancel()
                    outputs_log.append(f"[TIMEOUT at {elapsed:.1f}s: Cancelling execution]")
                    try:
                        kernel.interrupt()
                        outputs_log.append("[Sent interrupt signal to kernel]")
                    except Exception:
                        pass
                    break
                
                # Check for new outputs
                try:
                    current_outputs = ydoc._ycells[cell_index].get("outputs", [])
                    if len(current_outputs) > last_output_count:
                        new_outputs = current_outputs[last_output_count:]
                        for output in new_outputs:
                            extracted = extract_output(output)
                            if extracted.strip():
                                outputs_log.append(f"[{elapsed:.1f}s] {extracted}")
                        last_output_count = len(current_outputs)
                
                except Exception as e:
                    outputs_log.append(f"[{elapsed:.1f}s] Error checking outputs: {e}")
                
                # Progress update
                if int(elapsed) % progress_interval == 0 and elapsed > 0:
                    outputs_log.append(f"[PROGRESS: {elapsed:.1f}s elapsed, {last_output_count} outputs so far]")
                
                await asyncio.sleep(1)
            
            # Get final result
            if not execution_task.cancelled():
                try:
                    await execution_task
                    final_outputs = ydoc._ycells[cell_index].get("outputs", [])
                    outputs_log.append(f"[COMPLETED in {time.time() - start_time:.1f}s]")
                    
                    # Add any final outputs not captured during monitoring
                    if len(final_outputs) > last_output_count:
                        remaining = final_outputs[last_output_count:]
                        for output in remaining:
                            extracted = extract_output(output)
                            if extracted.strip():
                                outputs_log.append(extracted)
                                
                except Exception as e:
                    outputs_log.append(f"[ERROR: {e}]")
            
            return outputs_log if outputs_log else ["[No output generated]"]
            
        finally:
            if notebook:
                try:
                    await notebook.stop()
                except Exception as e:
                    outputs_log.append(f"[Warning: Error closing notebook: {e}]")
    
    return await __safe_notebook_operation(_execute_streaming, max_retries=1)

@mcp.tool()
async def read_all_cells() -> list[dict[str, Union[str, int, list[str]]]]:
    """Read all cells from the Jupyter notebook.
    Returns:
        list[dict]: List of cell information including index, type, source,
                    and outputs (for code cells)
    """
    async def _read_all():
        notebook = None
        try:
            notebook = NbModelClient(
                get_notebook_websocket_url(
                    server_url=ROOM_URL, token=ROOM_TOKEN, path=ROOM_ID, provider=PROVIDER
                )
            )
            await notebook.start()

            ydoc = notebook._doc
            cells = []

            for i, cell in enumerate(ydoc._ycells):
                cell_info = {
                    "index": i,
                    "type": cell.get("cell_type", "unknown"),
                    "source": cell.get("source", ""),
                }

                # Add outputs for code cells
                if cell.get("cell_type") == "code":
                    try:
                        outputs = cell.get("outputs", [])
                        cell_info["outputs"] = safe_extract_outputs(outputs)
                    except Exception as e:
                        cell_info["outputs"] = [f"[Error reading outputs: {str(e)}]"]

                cells.append(cell_info)

            return cells
        finally:
            if notebook:
                try:
                    await notebook.stop()
                except Exception as e:
                    logger.warning(f"Error stopping notebook in read_all_cells: {e}")
    
    return await __safe_notebook_operation(_read_all)


@mcp.tool()
async def read_cell(cell_index: int) -> dict[str, Union[str, int, list[str]]]:
    """Read a specific cell from the Jupyter notebook.
    Args:
        cell_index: Index of the cell to read (0-based)
    Returns:
        dict: Cell information including index, type, source, and outputs (for code cells)
    """
    async def _read_cell():
        notebook = None
        try:
            notebook = NbModelClient(
                get_notebook_websocket_url(
                    server_url=ROOM_URL, token=ROOM_TOKEN, path=ROOM_ID, provider=PROVIDER
                )
            )
            await notebook.start()

            ydoc = notebook._doc

            if cell_index < 0 or cell_index >= len(ydoc._ycells):
                raise ValueError(
                    f"Cell index {cell_index} is out of range. Notebook has {len(ydoc._ycells)} cells."
                )

            cell = ydoc._ycells[cell_index]
            cell_info = {
                "index": cell_index,
                "type": cell.get("cell_type", "unknown"),
                "source": cell.get("source", ""),
            }

            # Add outputs for code cells.
            if cell.get("cell_type") == "code":
                try:
                    outputs = cell.get("outputs", [])
                    cell_info["outputs"] = safe_extract_outputs(outputs)
                except Exception as e:
                    cell_info["outputs"] = [f"[Error reading outputs: {str(e)}]"]

            return cell_info
        finally:
            if notebook:
                try:
                    await notebook.stop()
                except Exception as e:
                    logger.warning(f"Error stopping notebook in read_cell: {e}")
    
    return await __safe_notebook_operation(_read_cell)


@mcp.tool()
async def get_notebook_info() -> dict[str, Union[str, int, dict[str, int]]]:
    """Get basic information about the notebook.
    Returns:
        dict: Notebook information including path, total cells, and cell type counts
    """
    async def _get_info():
        notebook = None
        try:
            notebook = NbModelClient(
                get_notebook_websocket_url(
                    server_url=ROOM_URL, token=ROOM_TOKEN, path=ROOM_ID, provider=PROVIDER
                )
            )
            await notebook.start()

            ydoc = notebook._doc
            total_cells: int = len(ydoc._ycells)

            cell_types: dict[str, int] = {}
            for cell in ydoc._ycells:
                cell_type: str = str(cell.get("cell_type", "unknown"))
                cell_types[cell_type] = cell_types.get(cell_type, 0) + 1

            info: dict[str, Union[str, int, dict[str, int]]] = {
                "room_id": ROOM_ID,
                "total_cells": total_cells,
                "cell_types": cell_types,
            }

            return info
        finally:
            if notebook:
                try:
                    await notebook.stop()
                except Exception as e:
                    logger.warning(f"Error stopping notebook in get_notebook_info: {e}")
    
    return await __safe_notebook_operation(_get_info)


@mcp.tool()
async def delete_cell(cell_index: int) -> str:
    """Delete a specific cell from the Jupyter notebook.
    Args:
        cell_index: Index of the cell to delete (0-based)
    Returns:
        str: Success message
    """
    async def _delete_cell():
        notebook = None
        try:
            notebook = NbModelClient(
                get_notebook_websocket_url(
                    server_url=ROOM_URL, token=ROOM_TOKEN, path=ROOM_ID, provider=PROVIDER
                )
            )
            await notebook.start()

            ydoc = notebook._doc

            if cell_index < 0 or cell_index >= len(ydoc._ycells):
                raise ValueError(
                    f"Cell index {cell_index} is out of range. Notebook has {len(ydoc._ycells)} cells."
                )

            cell_type = ydoc._ycells[cell_index].get("cell_type", "unknown")

            # Delete the cell
            del ydoc._ycells[cell_index]

            return f"Cell {cell_index} ({cell_type}) deleted successfully."
        finally:
            if notebook:
                try:
                    await notebook.stop()
                except Exception as e:
                    logger.warning(f"Error stopping notebook in delete_cell: {e}")
    
    return await __safe_notebook_operation(_delete_cell)


@mcp.tool()
async def create_notebook(notebook_path: str, initial_content: str = None, switch_to_notebook: bool = True) -> str:
    """Create a new Jupyter notebook at the specified path and optionally switch MCP context to it.
    
    Args:
        notebook_path: Path where to create the notebook (e.g., "analysis/my_notebook.ipynb")
        initial_content: Optional initial markdown content for the first cell
        switch_to_notebook: If True, switch the MCP server context to the new notebook (default: True)
    
    Returns:
        str: Success message with the created notebook path
    """
    async def _create_notebook():
        try:
            # Ensure the path ends with .ipynb
            if not notebook_path.endswith('.ipynb'):
                raise ValueError("Notebook path must end with '.ipynb'")
            
            # Create the basic notebook structure
            notebook_content = {
                "cells": [],
                "metadata": {
                    "kernelspec": {
                        "display_name": "Python 3",
                        "language": "python", 
                        "name": "python3"
                    },
                    "language_info": {
                        "name": "python",
                        "version": "3.10.0"
                    }
                },
                "nbformat": 4,
                "nbformat_minor": 4
            }
            
            # Add initial content if provided
            if initial_content:
                initial_cell = {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": initial_content
                }
                notebook_content["cells"].append(initial_cell)
            
            # Create the notebook using Jupyter Contents API
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {
                    "Content-Type": "application/json"
                }
                
                # Add authorization if token is provided
                if ROOM_TOKEN:
                    headers["Authorization"] = f"token {ROOM_TOKEN}"
                
                # Prepare the request data
                create_data = {
                    "type": "notebook",
                    "format": "json", 
                    "content": notebook_content
                }
                
                # Send PUT request to create the notebook
                response = await client.put(
                    f"{ROOM_URL}/api/contents/{notebook_path}",
                    json=create_data,
                    headers=headers
                )
                
                if response.status_code in [200, 201]:
                    result_data = response.json()
                    created_path = result_data.get("path", notebook_path)
                    
                    # Switch MCP server context to the new notebook if requested
                    if switch_to_notebook:
                        global ROOM_ID
                        old_room_id = ROOM_ID
                        ROOM_ID = created_path
                        logger.info(f"MCP server context switched from '{old_room_id}' to '{created_path}'")
                        
                        # Try to create a session for the new notebook to "warm it up"
                        try:
                            session_data = {
                                "path": created_path,
                                "type": "notebook",
                                "name": created_path,
                                "kernel": {"name": "python3"}
                            }
                            
                            session_response = await client.post(
                                f"{ROOM_URL}/api/sessions",
                                json=session_data,
                                headers=headers
                            )
                            
                            if session_response.status_code in [200, 201]:
                                logger.info(f"Session created for notebook: {created_path}")
                                session_info = session_response.json()
                                kernel_id = session_info.get("kernel", {}).get("id", "unknown")
                                # Generate the complete URL with token
                                if ROOM_TOKEN:
                                    notebook_url = f"{ROOM_URL}/lab/tree/{created_path}?token={ROOM_TOKEN}"
                                else:
                                    notebook_url = f"{ROOM_URL}/lab/tree/{created_path}"
                                
                                return f"Notebook created at: {created_path}. MCP context switched. Session & kernel ({kernel_id[:8]}...) started. ⚠️  OPEN: {notebook_url}"
                            else:
                                logger.warning(f"Failed to create session: {session_response.status_code}")
                                
                        except Exception as e:
                            logger.warning(f"Could not create session: {e}")
                        
                        # Generate the complete URL with token for fallback
                        if ROOM_TOKEN:
                            notebook_url = f"{ROOM_URL}/lab/tree/{created_path}?token={ROOM_TOKEN}"
                        else:
                            notebook_url = f"{ROOM_URL}/lab/tree/{created_path}"
                        
                        return f"Notebook created at: {created_path}. MCP server context switched to new notebook. ⚠️  IMPORTANT: Open this URL in your browser to establish collaboration: {notebook_url}"
                    else:
                        return f"Notebook created successfully at: {created_path}. MCP server context remains on current notebook."
                else:
                    # Try to get error details
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", f"HTTP {response.status_code}")
                    except:
                        error_msg = f"HTTP {response.status_code}: {response.text}"
                    
                    raise Exception(f"Failed to create notebook: {error_msg}")
                    
        except Exception as e:
            logger.error(f"Error creating notebook: {e}")
            raise
    
    return await __safe_notebook_operation(_create_notebook)


@mcp.tool()
async def switch_notebook(notebook_path: str, close_other_tabs: bool = True) -> str:
    """Switch the MCP server context to a different existing notebook and optionally manage browser tabs.
    
    Args:
        notebook_path: Path to the notebook to switch to (e.g., "analysis/my_notebook.ipynb")
        close_other_tabs: If True, provides URL that closes all other tabs and opens only this notebook
    
    Returns:
        str: Success message with URL for browser tab management
    """
    try:
        if not notebook_path.endswith('.ipynb'):
            raise ValueError("Notebook path must end with '.ipynb'")
        
        # First verify the notebook exists
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {}
            if ROOM_TOKEN:
                headers["Authorization"] = f"token {ROOM_TOKEN}"
            
            response = await client.get(
                f"{ROOM_URL}/api/contents/{notebook_path}",
                headers=headers
            )
            
            if response.status_code == 200:
                content_data = response.json()
                if content_data.get("type") == "notebook":
                    # Switch MCP context
                    global ROOM_ID
                    old_room_id = ROOM_ID
                    ROOM_ID = notebook_path
                    logger.info(f"MCP server context switched from '{old_room_id}' to '{notebook_path}'")
                    
                    # Generate URLs for different switching behaviors
                    base_url = f"{ROOM_URL}/lab/tree/{notebook_path}"
                    
                    if ROOM_TOKEN:
                        token_param = f"token={ROOM_TOKEN}"
                    else:
                        token_param = ""
                    
                    if close_other_tabs:
                        # Use reset parameter to close all tabs and open only this notebook
                        if token_param:
                            switch_url = f"{base_url}?reset&{token_param}"
                        else:
                            switch_url = f"{base_url}?reset"
                        
                        message = f"""MCP context switched to: {notebook_path}

🎯 **COMPLETE TAB MANAGEMENT**: Open this URL to close all other tabs and focus on this notebook:
{switch_url}

This URL will:
• ✅ Close ALL currently open notebook tabs
• ✅ Open ONLY the target notebook: {notebook_path}  
• ✅ Focus the browser on the new notebook
• ✅ Establish real-time MCP collaboration session"""
                        
                    else:
                        # Regular URL without closing other tabs
                        if token_param:
                            switch_url = f"{base_url}?{token_param}"
                        else:
                            switch_url = base_url
                        
                        message = f"""MCP context switched to: {notebook_path}

🔗 **OPEN NOTEBOOK**: Use this URL to open the notebook (keeps other tabs open):
{switch_url}

This will establish real-time MCP collaboration with the target notebook."""
                    
                    return message
                    
                else:
                    raise Exception(f"'{notebook_path}' is not a notebook file")
            elif response.status_code == 404:
                raise Exception(f"Notebook not found: {notebook_path}")
            else:
                raise Exception(f"Failed to access notebook: HTTP {response.status_code}")
                
    except Exception as e:
        logger.error(f"Error switching notebook: {e}")
        raise Exception(f"Failed to switch notebook: {e}")


@mcp.tool()
async def list_notebooks(directory_path: str = "", include_subdirectories: bool = True, max_depth: int = 3) -> Dict[str, Any]:
    """List all notebooks in the Jupyter workspace with metadata and paths.
    
    Args:
        directory_path: Specific directory to search (empty for root)
        include_subdirectories: Whether to search subdirectories
        max_depth: Maximum directory depth to search
        
    Returns:
        dict: Dictionary with notebook list and metadata
    """
    try:
        notebooks = []
        directories_scanned = []
        
        async def _scan_directory(path: str, current_depth: int = 0) -> None:
            if current_depth > max_depth:
                return
                
            try:
                directories_scanned.append(path)
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    headers = {}
                    if ROOM_TOKEN:
                        headers["Authorization"] = f"token {ROOM_TOKEN}"
                    
                    # Get directory contents
                    url = f"{ROOM_URL}/api/contents/{path}" if path else f"{ROOM_URL}/api/contents"
                    response = await client.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        content_data = response.json()
                        content_list = content_data.get("content", [])
                        
                        if isinstance(content_list, list):
                            for item in content_list:
                                if item.get("type") == "notebook" and item.get("name", "").endswith(".ipynb"):
                                    # Found a notebook
                                    notebook_info = {
                                        "name": item.get("name"),
                                        "path": item.get("path"),
                                        "created": item.get("created"),
                                        "last_modified": item.get("last_modified"),
                                        "size": item.get("size"),
                                        "writable": item.get("writable", True),
                                        "url": f"{ROOM_URL}/lab/tree/{item.get('path')}"
                                    }
                                    
                                    # Add token to URL if available
                                    if ROOM_TOKEN:
                                        notebook_info["url"] += f"?token={ROOM_TOKEN}"
                                    
                                    # Check if this is the current MCP notebook
                                    notebook_info["is_current_mcp_context"] = (item.get("path") == ROOM_ID)
                                    
                                    notebooks.append(notebook_info)
                                    
                                elif item.get("type") == "directory" and include_subdirectories:
                                    # Recursively scan subdirectory
                                    await _scan_directory(item.get("path", ""), current_depth + 1)
                                    
            except Exception as e:
                logger.warning(f"Error scanning directory '{path}': {e}")
        
        # Start scanning from the specified directory
        await _scan_directory(directory_path)
        
        # Sort notebooks by last modified (newest first)
        notebooks.sort(key=lambda x: x.get("last_modified", ""), reverse=True)
        
        result = {
            "notebooks": notebooks,
            "total_found": len(notebooks),
            "current_mcp_context": ROOM_ID,
            "directories_scanned": directories_scanned,
            "search_params": {
                "directory_path": directory_path or "root",
                "include_subdirectories": include_subdirectories,
                "max_depth": max_depth
            }
        }
        
        logger.info(f"Found {len(notebooks)} notebooks in workspace")
        return result
        
    except Exception as e:
        logger.error(f"Error listing notebooks: {e}")
        raise Exception(f"Failed to list notebooks: {e}")


@mcp.tool()
async def list_open_notebooks() -> Dict[str, Any]:
    """List all currently open notebooks in the JupyterLab interface.
    
    Returns:
        dict: Information about open notebooks and workspace state
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {}
            if ROOM_TOKEN:
                headers["Authorization"] = f"token {ROOM_TOKEN}"
            
            # Get current workspace data to see what's open
            response = await client.get(
                f"{ROOM_URL}/lab/api/workspaces/",
                headers=headers
            )
            
            if response.status_code == 200:
                workspaces_data = response.json()
                
                open_notebooks = []
                workspace_info = {}
                
                # Process workspaces to find open notebooks
                if "workspaces" in workspaces_data:
                    workspaces = workspaces_data["workspaces"]
                    
                    # Check the default workspace and named workspaces
                    all_workspaces = workspaces.get("values", [])
                    
                    for workspace in all_workspaces:
                        workspace_id = workspace.get("metadata", {}).get("id", "unknown")
                        workspace_data = workspace.get("data", {})
                        
                        # Look for notebook-related entries in the workspace data
                        notebook_entries = []
                        for key, value in workspace_data.items():
                            # Look for docmanager entries (open documents)
                            if "docmanager" in key.lower() or "notebook" in key.lower():
                                if isinstance(value, dict) and "data" in value:
                                    data = value["data"]
                                    if isinstance(data, dict) and "path" in data:
                                        path = data["path"]
                                        if path.endswith(".ipynb"):
                                            notebook_entries.append({
                                                "path": path,
                                                "factory": data.get("factory", "unknown"),
                                                "workspace_key": key
                                            })
                        
                        if notebook_entries:
                            workspace_info[workspace_id] = {
                                "open_notebooks": notebook_entries,
                                "total_open": len(notebook_entries)
                            }
                            open_notebooks.extend(notebook_entries)
                
                # Also get the default workspace specifically
                try:
                    default_response = await client.get(
                        f"{ROOM_URL}/lab/api/workspaces/lab",
                        headers=headers
                    )
                    if default_response.status_code == 200:
                        default_data = default_response.json()
                        workspace_data = default_data.get("data", {})
                        
                        for key, value in workspace_data.items():
                            if isinstance(value, dict) and "data" in value:
                                data = value["data"]
                                if isinstance(data, dict) and "path" in data:
                                    path = data["path"]
                                    if path.endswith(".ipynb"):
                                        # Avoid duplicates
                                        if not any(nb["path"] == path for nb in open_notebooks):
                                            open_notebooks.append({
                                                "path": path,
                                                "factory": data.get("factory", "unknown"),
                                                "workspace_key": key,
                                                "workspace": "default"
                                            })
                except:
                    pass  # Default workspace might not exist
                
                result = {
                    "open_notebooks": open_notebooks,
                    "total_open": len(open_notebooks),
                    "current_mcp_context": ROOM_ID,
                    "workspace_info": workspace_info,
                    "api_status": "success"
                }
                
                logger.info(f"Found {len(open_notebooks)} open notebooks in JupyterLab interface")
                return result
                
            else:
                raise Exception(f"Failed to access workspaces API: HTTP {response.status_code}")
                
    except Exception as e:
        logger.error(f"Error listing open notebooks: {e}")
        return {
            "open_notebooks": [],
            "total_open": 0,
            "current_mcp_context": ROOM_ID,
            "workspace_info": {},
            "api_status": "error",
            "error_message": str(e)
        }


@mcp.tool()
async def prepare_notebook(notebook_path: str) -> str:
    """Prepare a notebook for MCP collaboration by handling all setup automatically.
    
    This comprehensive tool will:
    - ✅ Check if the notebook exists
    - ✅ Switch MCP server context to the notebook
    - ✅ Create a focused workspace with ONLY the target notebook open
    - ✅ Provide URL to the focused workspace
    - ✅ Establish real-time collaboration session
    
    Args:
        notebook_path: Path to the notebook (e.g., "analysis/my_notebook.ipynb")
    
    Returns:
        str: Complete preparation status and browser URL for focused notebook work
    """
    global ROOM_ID, ROOM_URL, ROOM_TOKEN
    
    try:
        # Check if notebook exists
        async with httpx.AsyncClient() as client:
            # Build the Contents API URL
            contents_url = f"{ROOM_URL}/api/contents/{notebook_path}"
            headers = {}
            if ROOM_TOKEN:
                headers["Authorization"] = f"token {ROOM_TOKEN}"
            
            # Check if the notebook exists
            response = await client.get(contents_url, headers=headers)
            if response.status_code == 404:
                return f"❌ **ERROR**: Notebook '{notebook_path}' not found. Please check the path."
            elif response.status_code != 200:
                return f"❌ **ERROR**: Failed to access notebook '{notebook_path}'. Status: {response.status_code}"
            
            # Get notebook metadata
            notebook_info = response.json()
            size_kb = round(notebook_info.get('size', 0) / 1024, 1)
            last_modified = notebook_info.get('last_modified', 'Unknown')
            if last_modified != 'Unknown':
                # Parse and format the timestamp
                try:
                    dt = datetime.fromisoformat(last_modified.replace('Z', '+00:00'))
                    last_modified = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass
            
            # Update MCP context if needed
            context_switched = False
            if ROOM_ID != notebook_path:
                old_context = ROOM_ID
                ROOM_ID = notebook_path
                context_switched = True
            else:
                old_context = "same"
            
            # Create a focused workspace using the Workspaces API
            workspace_name = f"mcp-focused-{notebook_path.replace('/', '-').replace('.ipynb', '')}"
            
            # Define the workspace data with only the target notebook open
            workspace_data = {
                "data": {
                    f"application-mimedocuments:{notebook_path}:Notebook": {
                        "data": {"path": notebook_path, "factory": "Notebook"}
                    }
                },
                "metadata": {
                    "id": f"/lab/workspaces/{workspace_name}",
                    "last_modified": datetime.now().isoformat(),
                    "created": datetime.now().isoformat()
                }
            }
            
            # Save the focused workspace
            workspace_url = f"{ROOM_URL}/lab/api/workspaces/{workspace_name}"
            workspace_response = await client.put(
                workspace_url, 
                headers=headers,
                json=workspace_data
            )
            
            if workspace_response.status_code in [204, 200]:
                # Generate the focused workspace URL
                token_param = f"token={ROOM_TOKEN}" if ROOM_TOKEN else ""
                if token_param:
                    focused_url = f"{ROOM_URL}/lab/workspaces/{workspace_name}?{token_param}"
                else:
                    focused_url = f"{ROOM_URL}/lab/workspaces/{workspace_name}"
                
                # Prepare the success message
                result_message = f"""🎯 **NOTEBOOK PREPARATION COMPLETE**

📋 **Notebook Details**:
   • Path: {notebook_path}
   • Size: {size_kb}KB
   • Modified: {last_modified}
   • Status: ✅ Found and accessible

⚡ **MCP Setup**:
   • Context: {'✅ Switched to' if context_switched else '✅ Already set to'} '{notebook_path}'
   {f'• Previous: {old_context}' if context_switched and old_context != 'same' else ''}
   • Status: ✅ Ready for real-time collaboration

🎯 **FOCUSED WORKSPACE CREATED**:
   Click this URL to open ONLY the target notebook in a clean workspace:
   
   {focused_url}
   
   This focused workspace will:
   • 🗂️  Open ONLY the target notebook (no other tabs)
   • 🎯 Provide a clean, distraction-free environment
   • ⚡ Establish MCP collaboration session immediately
   • 💾 Save your focused workspace state automatically
   
✅ **Ready!** Your notebook is prepared for focused MCP-powered work.

💡 **Pro Tip**: Bookmark the focused workspace URL for quick access!"""
                
                return result_message
            else:
                # Fallback to regular URL if workspace creation fails
                logger.warning(f"Failed to create focused workspace: {workspace_response.status_code}")
                token_param = f"token={ROOM_TOKEN}" if ROOM_TOKEN else ""
                fallback_url = f"{ROOM_URL}/lab/tree/{notebook_path}?{token_param}" if token_param else f"{ROOM_URL}/lab/tree/{notebook_path}"
                
                return f"""🎯 **NOTEBOOK PREPARATION COMPLETE** (Fallback Mode)

📋 **Notebook Details**:
   • Path: {notebook_path}
   • Size: {size_kb}KB
   • Modified: {last_modified}
   • Status: ✅ Found and accessible

⚡ **MCP Setup**:
   • Context: {'✅ Switched to' if context_switched else '✅ Already set to'} '{notebook_path}'
   • Status: ✅ Ready for real-time collaboration

🔗 **NOTEBOOK URL**:
   {fallback_url}
   
⚠️  Note: Focused workspace creation failed, using standard URL instead."""
                
    except Exception as e:
        logger.error(f"Error in prepare_notebook: {e}")
        return f"❌ **ERROR**: Failed to prepare notebook '{notebook_path}'. Error: {str(e)}"


###############################################################################
# Commands.


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

    global RUNTIME_URL
    RUNTIME_URL = runtime_url
    global RUNTIME_ID
    RUNTIME_ID = runtime_id
    global RUNTIME_TOKEN
    RUNTIME_TOKEN = runtime_token

    global ROOM_URL
    ROOM_URL = room_url
    global ROOM_ID
    ROOM_ID = room_id
    global ROOM_TOKEN
    ROOM_TOKEN = room_token

    room_runtime = RoomRuntime(
        provider=PROVIDER,
        runtime_url=RUNTIME_URL,
        runtime_id=RUNTIME_ID,
        runtime_token=RUNTIME_TOKEN,
        room_url=ROOM_URL,
        room_id=ROOM_ID,
        room_token=ROOM_TOKEN,
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

    global RUNTIME_URL
    RUNTIME_URL = runtime_url
    global START_NEW_RUNTIME
    START_NEW_RUNTIME = start_new_runtime
    global RUNTIME_ID
    RUNTIME_ID = runtime_id
    global RUNTIME_TOKEN
    RUNTIME_TOKEN = runtime_token

    global ROOM_URL
    ROOM_URL = room_url
    global ROOM_ID
    ROOM_ID = room_id
    global ROOM_TOKEN
    ROOM_TOKEN = room_token

    if START_NEW_RUNTIME or RUNTIME_ID:
        try:
            __start_kernel()
        except Exception as e:
            logger.error(f"Failed to start kernel on startup: {e}")

    logger.info(f"Starting Jupyter MCP Server with transport: {transport}")

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "streamable-http":
        uvicorn.run(mcp.streamable_http_app, host="0.0.0.0", port=port)  # noqa: S104
    else:
        raise Exception("Transport should be `stdio` or `streamable-http`.")


###############################################################################
# Main.


if __name__ == "__main__":
    start_command()