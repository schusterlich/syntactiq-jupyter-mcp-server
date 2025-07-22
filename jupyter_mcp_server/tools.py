# Copyright (c) 2023-2024 Datalayer, Inc.
#
# BSD 3-Clause License

"""
MCP Tool Implementations for Jupyter Notebook Operations.

This module implements all the MCP tools that allow external clients
to interact with Jupyter notebooks through the Model Context Protocol.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Union, Dict, Any, List

import httpx
from mcp.server import FastMCP

import jupyter_mcp_server.config as config
import jupyter_mcp_server.server as server_module
from jupyter_mcp_server.server import (
    __ensure_kernel_alive, __ensure_notebook_connection,
    __start_notebook_connection, __execute_cell_and_wait_for_completion, 
    __wait_for_execution_outputs, __wait_for_cell_count_change, 
    __wait_for_cell_content_change, __safe_notebook_operation,
    __wait_for_kernel_idle
)
from jupyter_mcp_server.utils import extract_output, safe_extract_outputs, truncate_output, extract_image_info, safe_extract_outputs_with_images

logger = logging.getLogger(__name__)


def register_tools(mcp_server: FastMCP):
    """Register all MCP tools with the provided FastMCP server instance."""
    
    # Diagnostic tools
    mcp_server.tool()(debug_connection_status)
    
    # Cell manipulation tools
    mcp_server.tool()(append_markdown_cell)
    mcp_server.tool()(insert_markdown_cell)
    mcp_server.tool()(overwrite_cell_source)
    mcp_server.tool()(delete_cell)
    
    # Code execution tools
    mcp_server.tool()(append_execute_code_cell)
    mcp_server.tool()(insert_execute_code_cell)
    mcp_server.tool()(execute_cell_with_progress)
    mcp_server.tool()(execute_cell_simple_timeout)
    mcp_server.tool()(execute_cell_streaming)
    
    # Reading tools
    mcp_server.tool()(read_all_cells)
    mcp_server.tool()(read_cell)
    mcp_server.tool()(get_notebook_info)
    
    # Notebook management tools
    mcp_server.tool()(create_notebook)
    mcp_server.tool()(switch_notebook)
    mcp_server.tool()(list_notebooks)
    mcp_server.tool()(list_open_notebooks)
    mcp_server.tool()(prepare_notebook)


# Diagnostic Tools
# ================

async def debug_connection_status() -> dict:
    """Debug tool to check connection status and configuration values."""
    try:
        # Check configuration values
        debug_info = {
            "config": {
                "ROOM_URL": config.ROOM_URL,
                "ROOM_ID": config.ROOM_ID, 
                "ROOM_TOKEN": config.ROOM_TOKEN[:10] + "..." if config.ROOM_TOKEN else None,
                "PROVIDER": config.PROVIDER,
                "RUNTIME_URL": config.RUNTIME_URL,
            },
            "connection_status": {
                "kernel_status": "alive" if server_module.kernel and hasattr(server_module.kernel, 'is_alive') and server_module.kernel.is_alive() else "not_alive",
                "notebook_connection_exists": server_module.notebook_connection is not None,
                "notebook_connection_type": type(server_module.notebook_connection).__name__ if server_module.notebook_connection else "None",
            }
        }
        
        # Try to test notebook connection
        if server_module.notebook_connection:
            try:
                ydoc = server_module.notebook_connection._doc
                if ydoc:
                    debug_info["connection_status"]["doc_available"] = True
                    debug_info["connection_status"]["cell_count"] = len(ydoc._ycells) if hasattr(ydoc, '_ycells') else "unknown"
                else:
                    debug_info["connection_status"]["doc_available"] = False
                    debug_info["connection_status"]["doc_error"] = "ydoc is None"
            except Exception as e:
                debug_info["connection_status"]["doc_error"] = str(e)
        
        return debug_info
        
    except Exception as e:
        return {"error": f"Debug tool failed: {str(e)}"}


# Cell Manipulation Tools
# =======================


async def append_markdown_cell(cell_source: str) -> str:
    """Append at the end of the notebook a markdown cell with the provided source.

    Args:
        cell_source: Markdown source

    Returns:
        str: Success message (only returned after confirmed notebook synchronization)
    """
    async def _append_markdown():
        # Use persistent connection instead of creating new one
        await __ensure_notebook_connection()
        
        # Get initial cell count for synchronization
        ydoc = server_module.notebook_connection._doc
        initial_count = len(ydoc._ycells)
        expected_count = initial_count + 1
        
        # Perform the operation
        server_module.notebook_connection.add_markdown_cell(cell_source)
        
        # Wait for confirmation that cell was actually added
        if await __wait_for_cell_count_change(server_module.notebook_connection, expected_count):
            # Verify the cell content matches what we added
            final_ydoc = server_module.notebook_connection._doc
            added_cell = final_ydoc._ycells[initial_count]  # The newly added cell
            added_source = added_cell.get("source", "")
            if isinstance(added_source, list):
                added_source = ''.join(added_source)
            
            if cell_source.strip() in str(added_source).strip():
                return f"Jupyter Markdown cell added and confirmed at position {initial_count}."
            else:
                raise Exception("Cell added but content verification failed")
        else:
            raise Exception("Timeout waiting for cell addition confirmation")
    
    return await __safe_notebook_operation(_append_markdown)



async def insert_markdown_cell(cell_index: int, cell_source: str) -> str:
    """Insert a markdown cell in a Jupyter notebook.

    Args:
        cell_index: Index of the cell to insert (0-based)
        cell_source: Markdown source

    Returns:
        str: Success message (only returned after confirmed notebook synchronization)
    """
    async def _insert_markdown():
        # Use persistent connection instead of creating new one
        await __ensure_notebook_connection()
        
        # Get initial cell count for synchronization
        ydoc = server_module.notebook_connection._doc
        initial_count = len(ydoc._ycells)
        expected_count = initial_count + 1
        
        # Perform the operation
        server_module.notebook_connection.insert_markdown_cell(cell_index, cell_source)
        
        # Wait for confirmation that cell was actually inserted
        if await __wait_for_cell_count_change(server_module.notebook_connection, expected_count):
            # Verify the cell was inserted at correct position with correct content
            final_ydoc = server_module.notebook_connection._doc
            inserted_cell = final_ydoc._ycells[cell_index]  # The cell at insertion position
            inserted_source = inserted_cell.get("source", "")
            if isinstance(inserted_source, list):
                inserted_source = ''.join(inserted_source)
            
            if cell_source.strip() in str(inserted_source).strip():
                return f"Jupyter Markdown cell inserted and confirmed at position {cell_index}."
            else:
                raise Exception("Cell inserted but content verification failed")
        else:
            raise Exception("Timeout waiting for cell insertion confirmation")
    
    return await __safe_notebook_operation(_insert_markdown)



async def overwrite_cell_source(cell_index: int, cell_source: str) -> str:
    """Overwrite the source of an existing cell.
       Note this does not execute the modified cell by itself.

    Args:
        cell_index: Index of the cell to overwrite (0-based)
        cell_source: New cell source - must match existing cell type

    Returns:
        str: Success message (only returned after confirmed notebook synchronization)
    """
    async def _overwrite_cell():
        # Use persistent connection instead of creating new one
        await __ensure_notebook_connection()
        
        # Verify cell exists before attempting to overwrite
        ydoc = server_module.notebook_connection._doc
        if cell_index >= len(ydoc._ycells):
            raise Exception(f"Cell index {cell_index} out of range (notebook has {len(ydoc._ycells)} cells)")
        
        # Perform the operation
        server_module.notebook_connection.set_cell_source(cell_index, cell_source)
        
        # Wait for confirmation that cell content was actually updated
        if await __wait_for_cell_content_change(server_module.notebook_connection, cell_index, cell_source):
            return f"Cell {cell_index} overwritten successfully and confirmed - use execute_cell to execute it if code"
        else:
            raise Exception("Timeout waiting for cell content update confirmation")
    
    return await __safe_notebook_operation(_overwrite_cell)



async def append_execute_code_cell(cell_source: str, full_output: bool = False) -> Dict[str, Any]:
    """Append at the end of the notebook a code cell with the provided source and execute it.

    Args:
        cell_source: Code source
        full_output: If True, return complete execution outputs without truncation (default False)

    Returns:
        dict: Cell object with cell_index, cell_id, content, output, and images
    """
    async def _append_execute():
        await __ensure_kernel_alive()
        # Use persistent connection instead of creating new one
        await __ensure_notebook_connection()
        
        cell_index = server_module.notebook_connection.add_code_cell(cell_source)
        
        # Execute cell and wait for actual completion
        await __execute_cell_and_wait_for_completion(server_module.notebook_connection, cell_index, server_module.kernel)
        
        # Wait for outputs to be available
        await __wait_for_execution_outputs(server_module.notebook_connection, cell_index)
        
        # Now safely read the execution outputs with structured image handling
        ydoc = server_module.notebook_connection._doc
        cell = ydoc._ycells[cell_index]
        outputs = cell["outputs"]
        output_data = safe_extract_outputs_with_images(outputs, full_output)
        
        # Get cell ID if available
        cell_id = str(cell.get("id", f"cell-{cell_index}"))
        
        # Ensure content is serializable
        content = cell_source
        if hasattr(content, 'to_py'):
            content = content.to_py()
        content = str(content)
        
        return {
            "cell_index": cell_index,
            "cell_id": cell_id,
            "content": content,
            "output": output_data["text_outputs"],
            "images": output_data["images"]
        }
    
    return await __safe_notebook_operation(_append_execute)



async def insert_execute_code_cell(cell_index: int, cell_source: str, full_output: bool = False) -> Dict[str, Any]:
    """Insert and execute a code cell in a Jupyter notebook.

    Args:
        cell_index: Index of the cell to insert (0-based)
        cell_source: Code source
        full_output: If True, return complete execution outputs without truncation (default False)

    Returns:
        dict: Cell object with cell_index, cell_id, content, output, and images
    """
    async def _insert_execute():
        await __ensure_kernel_alive()
        # Use persistent connection instead of creating new one
        await __ensure_notebook_connection()
        
        server_module.notebook_connection.insert_code_cell(cell_index, cell_source)
        
        # Execute cell and wait for actual completion
        await __execute_cell_and_wait_for_completion(server_module.notebook_connection, cell_index, server_module.kernel)
        
        # Wait for outputs to be available
        await __wait_for_execution_outputs(server_module.notebook_connection, cell_index)
        
        # Now safely read the execution outputs with structured image handling
        ydoc = server_module.notebook_connection._doc
        cell = ydoc._ycells[cell_index]
        outputs = cell["outputs"]
        output_data = safe_extract_outputs_with_images(outputs, full_output)
        
        # Get cell ID if available
        cell_id = str(cell.get("id", f"cell-{cell_index}"))
        
        # Ensure content is serializable
        content = cell_source
        if hasattr(content, 'to_py'):
            content = content.to_py()
        content = str(content)
        
        return {
            "cell_index": cell_index,
            "cell_id": cell_id,
            "content": content,
            "output": output_data["text_outputs"],
            "images": output_data["images"]
        }
    
    return await __safe_notebook_operation(_insert_execute)



async def execute_cell_with_progress(cell_index: int, timeout_seconds: int = 300, full_output: bool = False) -> Dict[str, Any]:
    """Execute a specific cell with timeout and progress monitoring.
    Args:
        cell_index: Index of the cell to execute (0-based)
        timeout_seconds: Maximum time to wait for execution (default: 300s)
        full_output: If True, return complete execution outputs without truncation (default False)
    Returns:
        dict: {'text_outputs': list[str], 'images': list[dict]} - Clean text outputs and structured image data
    """
    async def _execute():
        await __ensure_kernel_alive()
        await __wait_for_kernel_idle(server_module.kernel, max_wait_seconds=30)
        
        # Use persistent connection instead of creating new one
        await __ensure_notebook_connection()

        ydoc = server_module.notebook_connection._doc

        if cell_index < 0 or cell_index >= len(ydoc._ycells):
            raise ValueError(
                f"Cell index {cell_index} is out of range. Notebook has {len(ydoc._ycells)} cells."
            )

        logger.info(f"Starting execution of cell {cell_index} with {timeout_seconds}s timeout")
        
        try:
            # Execute cell and wait for actual completion
            await __execute_cell_and_wait_for_completion(server_module.notebook_connection, cell_index, server_module.kernel, timeout_seconds)
            
            # Wait for outputs to be available
            await __wait_for_execution_outputs(server_module.notebook_connection, cell_index)

            # Get final outputs with structured image handling
            ydoc = server_module.notebook_connection._doc
            outputs = ydoc._ycells[cell_index]["outputs"]
            result = safe_extract_outputs_with_images(outputs, full_output)
            
            logger.info(f"Cell {cell_index} completed successfully with {len(result['text_outputs'])} text outputs and {len(result['images'])} images")
            return result
            
        except asyncio.TimeoutError as e:
            logger.error(f"Cell {cell_index} execution timed out: {e}")
            try:
                if server_module.kernel and hasattr(server_module.kernel, 'interrupt'):
                    server_module.kernel.interrupt()
                    logger.info("Sent interrupt signal to kernel")
            except Exception as interrupt_err:
                logger.error(f"Failed to interrupt kernel: {interrupt_err}")
            
            # Return partial outputs if available
            try:
                ydoc = server_module.notebook_connection._doc
                outputs = ydoc._ycells[cell_index].get("outputs", [])
                partial_result = safe_extract_outputs_with_images(outputs, full_output)
                partial_result["text_outputs"].append(f"[TIMEOUT ERROR: Execution exceeded {timeout_seconds} seconds]")
                return partial_result
            except Exception:
                pass
            
            return {
                "text_outputs": [f"[TIMEOUT ERROR: Cell execution exceeded {timeout_seconds} seconds and was interrupted]"],
                "images": []
            }
            
        except Exception as e:
            logger.error(f"Error executing cell {cell_index}: {e}")
            raise
        
    return await __safe_notebook_operation(_execute, max_retries=1)

# Simpler real-time monitoring without forced sync

async def execute_cell_simple_timeout(cell_index: int, timeout_seconds: int = 300, full_output: bool = False) -> Dict[str, Any]:
    """Execute a cell with simple timeout (no forced real-time sync). To be used for short-running cells.
    This won't force real-time updates but will work reliably.
    
    Args:
        cell_index: Index of the cell to execute (0-based)
        timeout_seconds: Maximum execution time in seconds (default 300)
        full_output: If True, return complete execution outputs without truncation (default False)
        
    Returns:
        dict: {'text_outputs': list[str], 'images': list[dict]} - Clean text outputs and structured image data
    """
    async def _execute():
        await __ensure_kernel_alive()
        await __wait_for_kernel_idle(server_module.kernel, max_wait_seconds=30)
        
        # Use persistent connection instead of creating new one
        await __ensure_notebook_connection()

        ydoc = server_module.notebook_connection._doc
        if cell_index < 0 or cell_index >= len(ydoc._ycells):
            raise ValueError(f"Cell index {cell_index} is out of range.")

        logger.info(f"Starting execution of cell {cell_index} with {timeout_seconds}s timeout")
        
        # Execute cell and wait for actual completion
        await __execute_cell_and_wait_for_completion(server_module.notebook_connection, cell_index, server_module.kernel, timeout_seconds)
        
        # Wait for outputs to be available
        await __wait_for_execution_outputs(server_module.notebook_connection, cell_index)

        # Get final outputs with structured image handling
        outputs = ydoc._ycells[cell_index]["outputs"]
        result = safe_extract_outputs_with_images(outputs, full_output)
        
        logger.info(f"Cell {cell_index} completed successfully")
        return result
    
    return await __safe_notebook_operation(_execute, max_retries=1)



async def execute_cell_streaming(cell_index: int, timeout_seconds: int = 300, progress_interval: int = 5, full_output: bool = False) -> list[str]:
    """Execute cell with streaming progress updates. To be used for long-running cells.
    Args:
        cell_index: Index of the cell to execute (0-based)
        timeout_seconds: Maximum time to wait for execution (default: 300s)  
        progress_interval: Seconds between progress updates (default: 5s)
        full_output: If True, return complete execution outputs without truncation (default False)
    Returns:
        list[str]: List of outputs including progress updates (truncated by default to 1000 chars for LLM context efficiency)
    """
    async def _execute_streaming():
        await __ensure_kernel_alive()
        await __wait_for_kernel_idle(server_module.kernel, max_wait_seconds=30)
        
        # Use persistent connection instead of creating new one
        await __ensure_notebook_connection()
        outputs_log = []

        ydoc = server_module.notebook_connection._doc
        if cell_index < 0 or cell_index >= len(ydoc._ycells):
            raise ValueError(f"Cell index {cell_index} is out of range.")

        # Start execution in background
        execution_task = asyncio.create_task(
            asyncio.to_thread(server_module.notebook_connection.execute_cell, cell_index, server_module.kernel)
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
                    server_module.kernel.interrupt()
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
                            truncated = truncate_output(extracted, full_output)
                            outputs_log.append(f"[{elapsed:.1f}s] {truncated}")
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
                            truncated = truncate_output(extracted, full_output)
                            outputs_log.append(truncated)
                            
            except Exception as e:
                outputs_log.append(f"[ERROR: {e}]")
        
        return outputs_log if outputs_log else ["[No output generated]"]
            
    return await __safe_notebook_operation(_execute_streaming, max_retries=1)


async def read_all_cells(full_output: bool = False) -> List[Dict[str, Any]]:
    """Read all cells from the Jupyter notebook with clean structured format.
    
    Args:
        full_output: If True, return complete cell outputs without truncation (default False)
        
    Returns:
        List[Dict[str, Any]]: Array of cell objects with consistent structure
    """
    async def _read_all():
        # Use persistent connection instead of creating new one
        await __ensure_notebook_connection()
        
        ydoc = server_module.notebook_connection._doc
        cells = []

        for i, cell in enumerate(ydoc._ycells):
            # Get cell ID if available (some Jupyter implementations have this)
            cell_id = str(cell.get("id", f"cell-{i}"))
            
            # Ensure content is properly serializable
            content = cell.get("source", "")
            if hasattr(content, 'to_py'):
                # Handle pycrdt Text objects
                content = content.to_py()
            if isinstance(content, list):
                content = ''.join(str(item) for item in content)
            else:
                content = str(content)
            
            cell_info = {
                "cell_index": i,
                "cell_id": cell_id,
                "content": content,
                "output": [],
                "images": []
            }

            # Add outputs for code cells with structured image handling
            if cell.get("cell_type") == "code":
                try:
                    outputs = cell.get("outputs", [])
                    output_data = safe_extract_outputs_with_images(outputs, full_output)
                    cell_info["output"] = output_data["text_outputs"]
                    cell_info["images"] = output_data["images"]
                except Exception as e:
                    cell_info["output"] = [f"[Error reading outputs: {str(e)}]"]

            cells.append(cell_info)

        return cells
    
    return await __safe_notebook_operation(_read_all)



async def read_cell(cell_index: int) -> Dict[str, Any]:
    """Read a specific cell from the Jupyter notebook with clean structured format.
    Args:
        cell_index: Index of the cell to read (0-based)
    Returns:
        dict: Cell object with cell_index, cell_id, content, output, and images
    """
    async def _read_cell():
        # Use persistent connection instead of creating new one
        await __ensure_notebook_connection()

        ydoc = server_module.notebook_connection._doc

        if cell_index < 0 or cell_index >= len(ydoc._ycells):
            raise ValueError(
                f"Cell index {cell_index} is out of range. Notebook has {len(ydoc._ycells)} cells."
            )

        cell = ydoc._ycells[cell_index]
        
        # Get cell ID if available
        cell_id = str(cell.get("id", f"cell-{cell_index}"))
        
        # Ensure content is properly serializable
        content = cell.get("source", "")
        if hasattr(content, 'to_py'):
            content = content.to_py()
        if isinstance(content, list):
            content = ''.join(str(item) for item in content)
        else:
            content = str(content)
        
        cell_info = {
            "cell_index": cell_index,
            "cell_id": cell_id,
            "content": content,
            "output": [],
            "images": []
        }

        # Add outputs for code cells with structured image handling
        if cell.get("cell_type") == "code":
            try:
                outputs = cell.get("outputs", [])
                output_data = safe_extract_outputs_with_images(outputs)
                cell_info["output"] = output_data["text_outputs"]
                cell_info["images"] = output_data["images"]
            except Exception as e:
                cell_info["output"] = [f"[Error reading outputs: {str(e)}]"]

        return cell_info
    
    return await __safe_notebook_operation(_read_cell)



async def get_notebook_info() -> dict[str, Union[str, int, dict[str, int]]]:
    """Get basic information about the notebook.
    Returns:
        dict: Notebook information including path, total cells, and cell type counts
    """
    async def _get_info():
        logger.info("get_notebook_info: Starting execution")
        
        # Use persistent connection instead of creating new one
        logger.info("get_notebook_info: Calling __ensure_notebook_connection()")
        await __ensure_notebook_connection()
        
        logger.info(f"get_notebook_info: Connection state after ensure: {server_module.notebook_connection is not None}")
        logger.info(f"get_notebook_info: Connection type: {type(server_module.notebook_connection) if server_module.notebook_connection else 'None'}")
        
        if server_module.notebook_connection is None:
            raise Exception("notebook_connection is None after __ensure_notebook_connection()")
        
        logger.info("get_notebook_info: Accessing _doc attribute")
        ydoc = server_module.notebook_connection._doc
        logger.info(f"get_notebook_info: Document retrieved: {ydoc is not None}")
        
        total_cells: int = len(ydoc._ycells)
        logger.info(f"get_notebook_info: Found {total_cells} cells")

        cell_types: dict[str, int] = {}
        for cell in ydoc._ycells:
            cell_type: str = str(cell.get("cell_type", "unknown"))
            cell_types[cell_type] = cell_types.get(cell_type, 0) + 1

        info: dict[str, Union[str, int, dict[str, int]]] = {
            "room_id": config.ROOM_ID,
            "total_cells": total_cells,
            "cell_types": cell_types,
        }

        logger.info(f"get_notebook_info: Returning result: {info}")
        return info
    
    return await __safe_notebook_operation(_get_info)



async def delete_cell(cell_index: int) -> str:
    """Delete a specific cell from the Jupyter notebook.
    Args:
        cell_index: Index of the cell to delete (0-based)
    Returns:
        str: Success message
    """
    async def _delete_cell():
        # Use persistent connection instead of creating new one
        await __ensure_notebook_connection()

        ydoc = server_module.notebook_connection._doc

        if cell_index < 0 or cell_index >= len(ydoc._ycells):
            raise ValueError(
                f"Cell index {cell_index} is out of range. Notebook has {len(ydoc._ycells)} cells."
            )

        cell_type = ydoc._ycells[cell_index].get("cell_type", "unknown")

        # Get initial count for synchronization verification
        initial_count = len(ydoc._ycells)
        expected_count = initial_count - 1
        
        # Delete the cell
        del ydoc._ycells[cell_index]
        
        # Wait for confirmation that cell was actually deleted
        if await __wait_for_cell_count_change(server_module.notebook_connection, expected_count):
            return f"Cell {cell_index} ({cell_type}) deleted successfully and confirmed."
        else:
            raise Exception("Timeout waiting for cell deletion confirmation")
    
    return await __safe_notebook_operation(_delete_cell)



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
                if config.ROOM_TOKEN:
                    headers["Authorization"] = f"token {config.ROOM_TOKEN}"
                
                # Prepare the request data
                create_data = {
                    "type": "notebook",
                    "format": "json", 
                    "content": notebook_content
                }
                
                # Send PUT request to create the notebook
                response = await client.put(
                    f"{config.ROOM_URL}/api/contents/{notebook_path}",
                    json=create_data,
                    headers=headers
                )
                
                if response.status_code in [200, 201]:
                    result_data = response.json()
                    created_path = result_data.get("path", notebook_path)
                    
                    # Switch MCP server context to the new notebook if requested
                    if switch_to_notebook:
                        old_room_id = config.ROOM_ID
                        config.ROOM_ID = created_path
                        logger.info(f"MCP server context switched from '{old_room_id}' to '{created_path}'")
                        # Restart notebook connection for new notebook
                        await __start_notebook_connection()
                        
                        # Try to create a session for the new notebook to "warm it up"
                        try:
                            session_data = {
                                "path": created_path,
                                "type": "notebook",
                                "name": created_path,
                                "kernel": {"name": "python3"}
                            }
                            
                            session_response = await client.post(
                                f"{config.ROOM_URL}/api/sessions",
                                json=session_data,
                                headers=headers
                            )
                            
                            if session_response.status_code in [200, 201]:
                                logger.info(f"Session created for notebook: {created_path}")
                                session_info = session_response.json()
                                kernel_id = session_info.get("kernel", {}).get("id", "unknown")
                                # Generate the complete URL with token
                                if config.ROOM_TOKEN:
                                    notebook_url = f"{config.ROOM_URL}/lab/tree/{created_path}?token={config.ROOM_TOKEN}"
                                else:
                                    notebook_url = f"{config.ROOM_URL}/lab/tree/{created_path}"
                                
                                return f"Notebook created at: {created_path}. MCP context switched. Session & kernel ({kernel_id[:8]}...) started. ⚠️  OPEN: {notebook_url}"
                            else:
                                logger.warning(f"Failed to create session: {session_response.status_code}")
                                
                        except Exception as e:
                            logger.warning(f"Could not create session: {e}")
                        
                        # Generate the complete URL with token for fallback
                        if config.ROOM_TOKEN:
                            notebook_url = f"{config.ROOM_URL}/lab/tree/{created_path}?token={config.ROOM_TOKEN}"
                        else:
                            notebook_url = f"{config.ROOM_URL}/lab/tree/{created_path}"
                        
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
            if config.ROOM_TOKEN:
                headers["Authorization"] = f"token {config.ROOM_TOKEN}"
            
            response = await client.get(
                f"{config.ROOM_URL}/api/contents/{notebook_path}",
                headers=headers
            )
            
            if response.status_code == 200:
                content_data = response.json()
                if content_data.get("type") == "notebook":
                    # Switch MCP context
                    old_room_id = config.ROOM_ID
                    config.ROOM_ID = notebook_path
                    logger.info(f"MCP server context switched from '{old_room_id}' to '{notebook_path}'")
                    # Restart notebook connection for new notebook
                    await __start_notebook_connection()
                    
                    # Generate URLs for different switching behaviors
                    base_url = f"{config.ROOM_URL}/lab/tree/{notebook_path}"
                    
                    if config.ROOM_TOKEN:
                        token_param = f"token={config.ROOM_TOKEN}"
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
                    if config.ROOM_TOKEN:
                        headers["Authorization"] = f"token {config.ROOM_TOKEN}"
                    
                    # Get directory contents
                    url = f"{config.ROOM_URL}/api/contents/{path}" if path else f"{config.ROOM_URL}/api/contents"
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
                                        "url": f"{config.ROOM_URL}/lab/tree/{item.get('path')}"
                                    }
                                    
                                    # Add token to URL if available
                                    if config.ROOM_TOKEN:
                                        notebook_info["url"] += f"?token={config.ROOM_TOKEN}"
                                    
                                    # Check if this is the current MCP notebook
                                    notebook_info["is_current_mcp_context"] = (item.get("path") == config.ROOM_ID)
                                    
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
            "current_mcp_context": config.ROOM_ID,
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



async def list_open_notebooks() -> Dict[str, Any]:
    """List all currently open notebooks in the JupyterLab interface.
    
    Returns:
        dict: Information about open notebooks and workspace state
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {}
            if config.ROOM_TOKEN:
                headers["Authorization"] = f"token {config.ROOM_TOKEN}"
            
            # Get current workspace data to see what's open
            response = await client.get(
                f"{config.ROOM_URL}/lab/api/workspaces/",
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
                        f"{config.ROOM_URL}/lab/api/workspaces/lab",
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
                    "current_mcp_context": config.ROOM_ID,
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
            "current_mcp_context": config.ROOM_ID,
            "workspace_info": {},
            "api_status": "error",
            "error_message": str(e)
        }



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
    # Configuration will be updated as needed
    
    try:
        # Check if notebook exists
        async with httpx.AsyncClient() as client:
            # Build the Contents API URL
            contents_url = f"{config.ROOM_URL}/api/contents/{notebook_path}"
            headers = {}
            if config.ROOM_TOKEN:
                headers["Authorization"] = f"token {config.ROOM_TOKEN}"
            
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
            if config.ROOM_ID != notebook_path:
                old_context = config.ROOM_ID
                config.ROOM_ID = notebook_path
                context_switched = True
                # Restart notebook connection for new notebook
                await __start_notebook_connection()
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
            workspace_url = f"{config.ROOM_URL}/lab/api/workspaces/{workspace_name}"
            workspace_response = await client.put(
                workspace_url, 
                headers=headers,
                json=workspace_data
            )
            
            if workspace_response.status_code in [204, 200]:
                # Generate the focused workspace URL
                token_param = f"token={config.ROOM_TOKEN}" if config.ROOM_TOKEN else ""
                if token_param:
                    focused_url = f"{config.ROOM_URL}/lab/workspaces/{workspace_name}?{token_param}"
                else:
                    focused_url = f"{config.ROOM_URL}/lab/workspaces/{workspace_name}"
                
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
                token_param = f"token={config.ROOM_TOKEN}" if config.ROOM_TOKEN else ""
                fallback_url = f"{config.ROOM_URL}/lab/tree/{notebook_path}?{token_param}" if token_param else f"{config.ROOM_URL}/lab/tree/{notebook_path}"
                
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