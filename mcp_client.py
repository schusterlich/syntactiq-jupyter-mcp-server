#!/usr/bin/env python3
"""
Jupyter MCP Client

A Python client for interacting with the Jupyter MCP Server via HTTP transport.
Handles response parsing, error handling, and provides a clean interface for
all MCP tools.
"""

import asyncio
import httpx
import json
from typing import Dict, Any, List


class MCPClient:
    """Client for interacting with the MCP server via HTTP"""
    
    def __init__(self, base_url: str = "http://localhost:4040"):
        self.base_url = base_url
        self.request_id = 0
    
    def _convert_char_array_to_string(self, data):
        """Convert character array to string if needed"""
        if isinstance(data, list) and len(data) > 0 and all(isinstance(c, str) and len(c) <= 1 for c in data):
            return ''.join(data)
        return data
    
    def _process_structured_content(self, structured_data):
        """Process structuredContent format from MCP response"""
        if isinstance(structured_data, dict):
            # Process each field in the dict
            result = {}
            for key, value in structured_data.items():
                if key == "source" and isinstance(value, list):
                    # Convert character array to string
                    result[key] = self._convert_char_array_to_string(value)
                elif isinstance(value, list):
                    # Process list items
                    result[key] = [self._process_structured_content(item) for item in value]
                elif isinstance(value, dict):
                    # Recursively process nested dicts
                    result[key] = self._process_structured_content(value)
                else:
                    result[key] = value
            return result
        elif isinstance(structured_data, list):
            # Process list of items (like cells)
            return [self._process_structured_content(item) for item in structured_data]
        else:
            return structured_data
    
    def _process_content(self, content_data):
        """Process content format from MCP response as fallback"""
        if isinstance(content_data, list) and len(content_data) > 0:
            # Try to parse the first text content
            first_content = content_data[0]
            if isinstance(first_content, dict) and first_content.get("type") == "text":
                try:
                    # Try to parse as JSON
                    return json.loads(first_content.get("text", "{}"))
                except json.JSONDecodeError:
                    return first_content.get("text", "")
        return content_data
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call an MCP tool via HTTP"""
        if arguments is None:
            arguments = {}
        
        self.request_id += 1
        
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
                response = await client.post(f"{self.base_url}/mcp", json=payload, headers=headers)
                response.raise_for_status()
                
                # Parse Server-Sent Events format
                response_text = response.text.strip()
                if "event: message" in response_text and "data: " in response_text:
                    # Extract JSON from SSE format
                    lines = response_text.split('\n')
                    json_str = ""
                    for line in lines:
                        if line.startswith("data: "):
                            json_str = line[6:]  # Remove "data: " prefix
                            break
                    if json_str:
                        result = json.loads(json_str)
                    else:
                        raise Exception("Could not find JSON data in SSE response")
                else:
                    # Fallback to direct JSON parsing
                    result = response.json()
                
                if "error" in result:
                    raise Exception(f"MCP Error: {result['error']}")
                
                # Extract the actual result data, preferring structuredContent over content
                mcp_result = result.get("result", {})
                if "structuredContent" in mcp_result:
                    return self._process_structured_content(mcp_result["structuredContent"])
                elif "content" in mcp_result:
                    # Fallback to content parsing if no structuredContent
                    return self._process_content(mcp_result["content"])
                else:
                    return mcp_result
                
            except httpx.RequestError as e:
                raise Exception(f"Request failed: {e}")
            except httpx.HTTPStatusError as e:
                raise Exception(f"HTTP error {e.response.status_code}: {e.response.text}")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available MCP tools"""
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id + 1,
            "method": "tools/list"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Content-Type": "application/json", 
                "Accept": "application/json, text/event-stream"
            }
            response = await client.post(f"{self.base_url}/mcp", json=payload, headers=headers)
            response.raise_for_status()
            
            # Parse Server-Sent Events format
            response_text = response.text.strip()
            if "event: message" in response_text and "data: " in response_text:
                # Extract JSON from SSE format
                lines = response_text.split('\n')
                json_str = ""
                for line in lines:
                    if line.startswith("data: "):
                        json_str = line[6:]  # Remove "data: " prefix
                        break
                if json_str:
                    result = json.loads(json_str)
                else:
                    raise Exception("Could not find JSON data in SSE response")
            else:
                # Fallback to direct JSON parsing
                result = response.json()
            
            # Process the tools list with proper parsing
            tools_result = result.get("result", {})
            if "tools" in tools_result:
                return tools_result["tools"]
            else:
                return []
    
    # Convenience methods for common operations
    async def get_notebook_info(self) -> Dict[str, Any]:
        """Get notebook information"""
        return await self.call_tool("get_notebook_info")
    
    async def read_all_cells(self, full_output: bool = False) -> List[Dict[str, Any]]:
        """Read all cells from the notebook
        
        Args:
            full_output: If True, return complete cell outputs without truncation (default False)
        """
        arguments = {"full_output": full_output}
        result = await self.call_tool("read_all_cells", arguments)
        # Handle the {"result": [...]} format
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        elif isinstance(result, list):
            return result
        else:
            return [result] if result else []
    
    async def read_cell(self, cell_index: int) -> Dict[str, Any]:
        """Read a specific cell"""
        return await self.call_tool("read_cell", {"cell_index": cell_index})
    
    async def append_markdown_cell(self, cell_source: str) -> str:
        """Add a markdown cell to the end of the notebook"""
        result = await self.call_tool("append_markdown_cell", {"cell_source": cell_source})
        # Extract the actual message
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        else:
            return str(result)
    
    async def insert_markdown_cell(self, cell_index: int, cell_source: str) -> str:
        """Insert a markdown cell at a specific position"""
        result = await self.call_tool("insert_markdown_cell", {
            "cell_index": cell_index,
            "cell_source": cell_source
        })
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        else:
            return str(result)
    
    async def append_execute_code_cell(self, cell_source: str, full_output: bool = False) -> List[str]:
        """Add and execute a code cell at the end of the notebook
        
        Args:
            cell_source: Code to execute
            full_output: If True, return complete execution outputs without truncation (default False)
        """
        arguments = {
            "cell_source": cell_source,
            "full_output": full_output
        }
        result = await self.call_tool("append_execute_code_cell", arguments)
        # Process execution results
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        elif isinstance(result, list):
            return result
        else:
            return [result]
    
    async def insert_execute_code_cell(self, cell_index: int, cell_source: str, full_output: bool = False) -> List[str]:
        """Insert and execute a code cell at a specific position
        
        Args:
            cell_index: Position to insert the cell
            cell_source: Code to execute
            full_output: If True, return complete execution outputs without truncation (default False)
        """
        result = await self.call_tool("insert_execute_code_cell", {
            "cell_index": cell_index,
            "cell_source": cell_source,
            "full_output": full_output
        })
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        elif isinstance(result, list):
            return result
        else:
            return [result]
    
    async def execute_cell_with_progress(self, cell_index: int, timeout_seconds: int = 300, full_output: bool = False) -> List[str]:
        """Execute a cell with progress monitoring
        
        Args:
            cell_index: Index of cell to execute
            timeout_seconds: Maximum execution time
            full_output: If True, return complete execution outputs without truncation (default False)
        """
        result = await self.call_tool("execute_cell_with_progress", {
            "cell_index": cell_index,
            "timeout_seconds": timeout_seconds,
            "full_output": full_output
        })
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        elif isinstance(result, list):
            return result
        else:
            return [result]
    
    async def execute_cell_simple_timeout(self, cell_index: int, timeout_seconds: int = 300, full_output: bool = False) -> List[str]:
        """Execute a cell with simple timeout
        
        Args:
            cell_index: Index of cell to execute
            timeout_seconds: Maximum execution time
            full_output: If True, return complete execution outputs without truncation (default False)
        """
        result = await self.call_tool("execute_cell_simple_timeout", {
            "cell_index": cell_index,
            "timeout_seconds": timeout_seconds,
            "full_output": full_output
        })
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        elif isinstance(result, list):
            return result
        else:
            return [result]
    
    async def execute_cell_streaming(self, cell_index: int, timeout_seconds: int = 300, progress_interval: int = 5, full_output: bool = False) -> List[str]:
        """Execute a cell with streaming progress updates
        
        Args:
            cell_index: Index of cell to execute
            timeout_seconds: Maximum execution time
            progress_interval: Seconds between progress updates
            full_output: If True, return complete execution outputs without truncation (default False)
        """
        result = await self.call_tool("execute_cell_streaming", {
            "cell_index": cell_index,
            "timeout_seconds": timeout_seconds,
            "progress_interval": progress_interval,
            "full_output": full_output
        })
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        elif isinstance(result, list):
            return result
        else:
            return [result]
    
    async def overwrite_cell_source(self, cell_index: int, cell_source: str) -> str:
        """Overwrite the source of an existing cell"""
        result = await self.call_tool("overwrite_cell_source", {
            "cell_index": cell_index,
            "cell_source": cell_source
        })
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        else:
            return str(result)
    
    async def delete_cell(self, cell_index: int) -> str:
        """Delete a cell from the notebook"""
        result = await self.call_tool("delete_cell", {"cell_index": cell_index})
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        else:
            return str(result)
    
    async def create_notebook(self, notebook_path: str, initial_content: str = None, switch_to_notebook: bool = True) -> str:
        """Create a new Jupyter notebook at the specified path
        
        Args:
            notebook_path: Path where to create the notebook (e.g., "analysis/my_notebook.ipynb")
            initial_content: Optional initial markdown content for the first cell
            switch_to_notebook: If True, switch the MCP server context to the new notebook (default: True)
            
        Returns:
            str: Success message with the created notebook path
        """
        arguments = {"notebook_path": notebook_path, "switch_to_notebook": switch_to_notebook}
        if initial_content is not None:
            arguments["initial_content"] = initial_content
            
        result = await self.call_tool("create_notebook", arguments)
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        else:
            return str(result)
    
    async def switch_notebook(self, notebook_path: str, close_other_tabs: bool = True) -> str:
        """Switch the MCP server context to a different existing notebook with tab management"""
        arguments = {"notebook_path": notebook_path, "close_other_tabs": close_other_tabs}
        result = await self.call_tool("switch_notebook", arguments)
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        else:
            return str(result)

    async def list_open_notebooks(self) -> Dict[str, Any]:
        """List all currently open notebooks in the JupyterLab interface"""
        result = await self.call_tool("list_open_notebooks")
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        else:
            return result

    async def prepare_notebook(self, notebook_path: str) -> str:
        """Prepare a notebook for MCP collaboration with comprehensive setup.
        
        This handles:
        - Checking if notebook exists
        - Switching MCP context
        - Providing focused browser URL (closes other tabs)
        - Setting up collaboration session
        """
        result = await self.call_tool("prepare_notebook", {"notebook_path": notebook_path})
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        else:
            return str(result)

    async def execute_with_progress(self, cell_index: int, timeout_seconds: int = 300, full_output: bool = False) -> list:
        """Execute a cell with progress monitoring
        
        Args:
            cell_index: Index of cell to execute
            timeout_seconds: Maximum execution time
            full_output: If True, return complete execution outputs without truncation (default False)
        """
        result = await self.call_tool("execute_cell_with_progress", {
            "cell_index": cell_index,
            "timeout_seconds": timeout_seconds,
            "full_output": full_output
        })
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "result" in result:
            return result["result"] if isinstance(result["result"], list) else [result["result"]]
        else:
            return [str(result)]

    async def list_notebooks(self, directory_path: str = "", include_subdirectories: bool = True, max_depth: int = 3) -> Dict[str, Any]:
        """List all notebooks in the Jupyter workspace with metadata"""
        arguments = {
            "directory_path": directory_path,
            "include_subdirectories": include_subdirectories,
            "max_depth": max_depth
        }
        result = await self.call_tool("list_notebooks", arguments)
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        else:
            return result 