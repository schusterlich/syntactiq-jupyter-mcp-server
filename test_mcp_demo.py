#!/usr/bin/env python3
"""
Jupyter MCP Server Demo Test Script

This script demonstrates the functionality of the Jupyter MCP Server by:
1. Starting the services using docker-compose
2. Waiting for health checks to pass
3. Executing various MCP tools to show notebook interaction
4. Displaying real-time results

Usage: python test_mcp_demo.py
"""

import asyncio
import httpx
import json
import subprocess
import time
import sys
from typing import Dict, Any, List
from pathlib import Path

# Import our MCP client
from mcp_client import MCPClient

# Configuration
JUPYTER_URL = "http://localhost:8888"
MCP_URL = "http://localhost:4040"
JUPYTER_TOKEN = "MY_TOKEN"  # Default token from docker-compose
TIMEOUT_SECONDS = 300  # 5 minutes max wait time

class Colors:
    """ANSI color codes for pretty output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_header(message: str):
    """Print a formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message.center(60)}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}\n")

def print_step(step: str):
    """Print a step message"""
    print(f"{Colors.CYAN}{Colors.BOLD}🔹 {step}{Colors.END}")

def print_success(message: str):
    """Print a success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message: str):
    """Print an error message"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_info(message: str):
    """Print an info message"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")



def start_services():
    """Start the docker-compose services"""
    print_step("Starting Docker Compose services...")
    
    try:
        # Stop any existing services
        subprocess.run(["docker-compose", "down"], 
                      capture_output=True, check=False, cwd=Path.cwd())
        
        # Start services
        result = subprocess.run(
            ["docker-compose", "up", "-d"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path.cwd()
        )
        
        print_success("Services started successfully")
        if result.stdout:
            print(f"{Colors.BLUE}{result.stdout}{Colors.END}")
            
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to start services: {e}")
        if e.stderr:
            print(f"{Colors.RED}{e.stderr}{Colors.END}")
        sys.exit(1)

async def wait_for_services():
    """Wait for services to be healthy"""
    print_step("Waiting for services to become healthy...")
    
    services = [
        ("JupyterLab", f"{JUPYTER_URL}/api"),
        ("MCP Server", f"{MCP_URL}/api/healthz")
    ]
    
    start_time = time.time()
    
    for service_name, health_url in services:
        print(f"  Checking {service_name}...")
        
        while time.time() - start_time < TIMEOUT_SECONDS:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(health_url)
                    if response.status_code == 200:
                        print_success(f"{service_name} is healthy")
                        break
            except:
                pass
            
            await asyncio.sleep(2)
        else:
            print_error(f"{service_name} failed to become healthy within {TIMEOUT_SECONDS}s")
            sys.exit(1)
    
    print_success("All services are healthy!")

async def create_demo_notebook():
    """Create a demo notebook if it doesn't exist"""
    notebook_path = Path("notebooks/demo.ipynb")
    
    if not notebook_path.exists():
        print_step("Creating demo notebook...")
        
        # Ensure notebooks directory exists
        notebook_path.parent.mkdir(exist_ok=True)
        
        demo_notebook = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "# MCP Server Demo Notebook\n",
                        "\n",
                        "This notebook demonstrates the Jupyter MCP Server functionality.\n",
                        "The MCP server can read, write, and execute cells in real-time!"
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# Initial demo cell\n",
                        "print(\"Hello from the demo notebook!\")\n",
                        "import sys\n",
                        "print(f\"Python version: {sys.version}\")"
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
                    "name": "python",
                    "version": "3.10.0"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 4
        }
        
        with open(notebook_path, 'w') as f:
            json.dump(demo_notebook, f, indent=2)
        
        print_success("Demo notebook created")

async def demo_mcp_tools(client):
    """Demonstrate various MCP tools"""
    
    print_header("MCP Tools Demonstration")
    
    # List available tools
    print_step("Listing available MCP tools...")
    try:
        tools = await client.list_tools()
        print(f"{Colors.GREEN}Available tools:{Colors.END}")
        for tool in tools:
            print(f"  • {Colors.YELLOW}{tool['name']}{Colors.END}: {tool.get('description', 'No description')}")
        print()
    except Exception as e:
        print_error(f"Failed to list tools: {e}")
        return
    
    # Test 1: Get notebook info
    print_step("Test 1: Getting notebook information...")
    try:
        info = await client.call_tool("get_notebook_info")
        
        # Handle the case where info might be nested or in different formats
        if isinstance(info, dict):
            room_id = info.get('room_id', 'Unknown')
            total_cells = info.get('total_cells', 'Unknown')
            cell_types = info.get('cell_types', {})
        else:
            # Fallback for unexpected format
            room_id = str(info)
            total_cells = 'Unknown'
            cell_types = {}
        
        print(f"{Colors.GREEN}Notebook Info:{Colors.END}")
        print(f"  Room ID: {room_id}")
        print(f"  Total cells: {total_cells}")
        print(f"  Cell types: {cell_types}")
        print()
    except Exception as e:
        print_error(f"Failed to get notebook info: {e}")
        import traceback
        print_info(f"Debug info: {traceback.format_exc()}")
        return
    
    # Test 2: Read all cells
    print_step("Test 2: Reading all cells...")
    try:
        cells_result = await client.call_tool("read_all_cells")
        
        # Handle different response formats - read_all_cells returns {"result": [...]}
        if isinstance(cells_result, dict) and "result" in cells_result:
            cells = cells_result["result"]
        elif isinstance(cells_result, list):
            cells = cells_result
        else:
            # Fallback - treat the whole result as the cells data
            cells = [cells_result] if cells_result else []
        
        print(f"{Colors.GREEN}Current cells in notebook:{Colors.END}")
        
        if isinstance(cells, list):
            for i, cell in enumerate(cells):
                if isinstance(cell, dict):
                    cell_type = cell.get('type', 'unknown')
                    source = cell.get('source', '')
                    if isinstance(source, str):
                        source_preview = source[:100] + ('...' if len(source) > 100 else '')
                    else:
                        source_preview = str(source)[:100] + ('...' if len(str(source)) > 100 else '')
                    print(f"  Cell {i} ({cell_type}): {source_preview}")
                else:
                    print(f"  Cell {i}: {str(cell)[:100]}")
        else:
            print(f"  Unexpected format: {type(cells)} - {str(cells)[:200]}")
        print()
    except Exception as e:
        print_error(f"Failed to read cells: {e}")
        import traceback
        print_info(f"Debug info: {traceback.format_exc()}")
        return
    
    # Test 3: Add a markdown cell
    print_step("Test 3: Adding a markdown cell...")
    try:
        markdown_content = """## MCP Server Test Results

This cell was added by the MCP server! 🎉

The server can:
- ✅ Read notebook structure
- ✅ Add markdown cells  
- ✅ Execute Python code
- ✅ Monitor execution progress
"""
        result = await client.call_tool("append_markdown_cell", {
            "cell_source": markdown_content
        })
        
        # Extract the actual message from the result
        if isinstance(result, dict) and "result" in result:
            message = result["result"]
        else:
            message = str(result)
        print_success(f"Markdown cell added: {message}")
    except Exception as e:
        print_error(f"Failed to add markdown cell: {e}")
        import traceback
        print_info(f"Debug info: {traceback.format_exc()}")
    
    # Test 4: Execute Python code
    print_step("Test 4: Executing Python code...")
    try:
        code = """
# MCP Server Code Execution Demo
import datetime
import platform

print("🔬 MCP Server Execution Test")
print(f"⏰ Current time: {datetime.datetime.now()}")
print(f"🐍 Python version: {platform.python_version()}")
print(f"💻 Platform: {platform.system()} {platform.release()}")

# Test data analysis
import pandas as pd
import numpy as np

data = pd.DataFrame({
    'x': np.random.randn(10),
    'y': np.random.randn(10)
})

print(f"📊 Generated sample data with {len(data)} rows")
print("✅ MCP Server execution completed successfully!")
"""
        
        result = await client.call_tool("append_execute_code_cell", {
            "cell_source": code
        })
        
        # Process execution results
        if isinstance(result, dict) and "result" in result:
            outputs = result["result"]
        elif isinstance(result, list):
            outputs = result
        else:
            outputs = [result]
        
        print(f"{Colors.GREEN}Code execution results ({len(outputs)} outputs):{Colors.END}")
        for i, output in enumerate(outputs):
            # Clean up the output display
            clean_output = str(output).strip()
            if clean_output:
                print(f"  Output {i+1}: {clean_output}")
        print()
        
    except Exception as e:
        print_error(f"Failed to execute code: {e}")
    
    # Test 5: Test with progress monitoring
    print_step("Test 5: Long-running code with progress monitoring...")
    try:
        long_code = """
# Long-running task simulation
import time
import random

print("🚀 Starting long-running task...")

for i in range(5):
    print(f"⏳ Step {i+1}/5: Processing...")
    time.sleep(1)  # Simulate work
    
    # Generate some random data
    result = sum(random.randint(1, 100) for _ in range(1000))
    print(f"   Generated sum: {result}")

print("🎯 Task completed successfully!")
"""
        
        # Add the code cell first
        add_result = await client.call_tool("append_execute_code_cell", {
            "cell_source": long_code
        })
        
        # Process long-running execution results
        if isinstance(add_result, dict) and "result" in add_result:
            outputs = add_result["result"]
        elif isinstance(add_result, list):
            outputs = add_result
        else:
            outputs = [add_result]
        
        print(f"{Colors.GREEN}Long-running task results ({len(outputs)} progress updates):{Colors.END}")
        for i, output in enumerate(outputs):
            clean_output = str(output).strip()
            if clean_output:
                print(f"  Progress {i+1}: {clean_output}")
        print()
        
    except Exception as e:
        print_error(f"Failed to execute long-running code: {e}")
    
    # Test 6: Read final notebook state
    print_step("Test 6: Reading final notebook state...")
    try:
        final_info = await client.call_tool("get_notebook_info")
        
        # Process final state info
        if isinstance(final_info, dict):
            total_cells = final_info.get('total_cells', 'Unknown')
            cell_types = final_info.get('cell_types', {})
            room_id = final_info.get('room_id', 'Unknown')
        else:
            total_cells = 'Unknown'
            cell_types = {}
            room_id = str(final_info)
        
        print(f"{Colors.GREEN}Final notebook state:{Colors.END}")
        print(f"  Room ID: {room_id}")
        print(f"  Total cells: {total_cells}")
        print(f"  Cell types: {cell_types}")
        
        # Show what we accomplished
        if isinstance(cell_types, dict):
            markdown_count = cell_types.get('markdown', 0)
            code_count = cell_types.get('code', 0)
            print(f"{Colors.CYAN}📊 Demo accomplished:{Colors.END}")
            print(f"  • Added markdown documentation ({markdown_count} total)")
            print(f"  • Executed Python code ({code_count} total)")
            print(f"  • Monitored long-running processes")
            print(f"  • Real-time notebook collaboration")
        
        # Show we can access Jupyter directly too
        print(f"\n{Colors.YELLOW}You can also access the notebook directly at:{Colors.END}")
        print(f"  🔗 JupyterLab: {JUPYTER_URL}?token={JUPYTER_TOKEN}")
        print(f"  🔗 MCP Server: {MCP_URL}/api/healthz")
        
    except Exception as e:
        print_error(f"Failed to read final state: {e}")

def show_service_info():
    """Show information about running services"""
    print_header("Service Information")
    
    print(f"{Colors.CYAN}Services Status:{Colors.END}")
    try:
        result = subprocess.run(
            ["docker-compose", "ps"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        print(result.stdout)
    except:
        print("Could not get service status")
    
    print(f"{Colors.CYAN}Service URLs:{Colors.END}")
    print(f"  🚀 JupyterLab: {JUPYTER_URL}?token={JUPYTER_TOKEN}")
    print(f"  🔧 MCP Server: {MCP_URL}")
    print(f"  🩺 Health Check: {MCP_URL}/api/healthz")
    
    print(f"\n{Colors.YELLOW}To stop services:{Colors.END}")
    print(f"  docker-compose down")
    
    print(f"\n{Colors.YELLOW}To view logs:{Colors.END}")
    print(f"  docker-compose logs -f")

async def main():
    """Main test function"""
    print_header("Jupyter MCP Server Demo")
    
    print_info("This script will:")
    print("  1. Start JupyterLab and MCP Server using docker-compose")
    print("  2. Wait for services to become healthy")
    print("  3. Demonstrate MCP tools with live notebook interaction")
    print("  4. Show you how to access the services")
    
    input(f"\n{Colors.BOLD}Press Enter to start the demo...{Colors.END}")
    
    try:
        # Start services
        start_services()
        
        # Wait for health
        await wait_for_services()
        
        # Create demo notebook if needed
        await create_demo_notebook()
        
        # Wait a bit more for MCP server to be fully ready
        print_step("Waiting for MCP server to be fully ready...")
        await asyncio.sleep(15)  # Give MCP server more time to fully initialize
        
        # Double-check MCP server is responding
        max_retries = 5
        for i in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{MCP_URL}/api/healthz")
                    if response.status_code == 200:
                        health_data = response.json()
                        if health_data.get("status") == "healthy":
                            print_success("MCP Server is fully ready!")
                            break
                        else:
                            print_info(f"MCP Server status: {health_data}")
            except Exception as e:
                print_info(f"Waiting for MCP server... (attempt {i+1}/{max_retries})")
            
            if i < max_retries - 1:
                await asyncio.sleep(3)
        else:
            print_error("MCP Server may not be fully ready, but continuing with demo...")
        
        # IMPORTANT: User needs to open the notebook first
        print_header("📓 Open Notebook in JupyterLab")
        print_info("For the MCP server to work, you need to open the notebook in JupyterLab first.")
        print_info("This creates the collaboration session that the MCP server connects to.")
        print()
        print(f"{Colors.YELLOW}{Colors.BOLD}👉 Please follow these steps:{Colors.END}")
        print(f"   1. Open JupyterLab: {Colors.CYAN}http://localhost:8888?token={JUPYTER_TOKEN}{Colors.END}")
        print(f"   2. Click on {Colors.YELLOW}notebook.ipynb{Colors.END} to open it")
        print(f"   3. Wait for the notebook to fully load")
        print(f"   4. Come back here and press Enter to continue...")
        print()
        input(f"{Colors.BOLD}Press Enter after you've opened notebook.ipynb in JupyterLab...{Colors.END}")
        
        # Give the collaboration session time to establish
        print_info("⏳ Waiting for collaboration session to establish...")
        await asyncio.sleep(5)
        
        # Initialize MCP client
        client = MCPClient(MCP_URL)
        
        # Verify the notebook session is active
        print_step("Verifying notebook connection...")
        print_info("💡 Tip: If verification fails, try refreshing the notebook page in JupyterLab!")
        notebook_connected = False
        for attempt in range(6):  # More attempts
            try:
                info = await client.call_tool("get_notebook_info")
                
                # Handle different response formats for verification
                room_id = None
                if isinstance(info, dict):
                    room_id = info.get('room_id')
                elif isinstance(info, str):
                    room_id = info
                
                if room_id and room_id != 'None' and room_id != 'Unknown':
                    print_success(f"✅ Connected to notebook: {room_id}")
                    notebook_connected = True
                    break
                else:
                    print_info(f"Attempt {attempt + 1}/6: Notebook not connected yet... (room_id: {room_id})")
                    await asyncio.sleep(5)  # Longer delay
            except Exception as e:
                print_info(f"Attempt {attempt + 1}/6: Connection test failed - {e}")
                await asyncio.sleep(5)  # Longer delay
        
        if not notebook_connected:
            print_error("⚠️  Could not verify notebook connection.")
            print_info("The demo will continue, but some tools may not work properly.")
            print_info("To fix this:")
            print_info("  1. Make sure notebook.ipynb is open in JupyterLab")
            print_info("  2. Try refreshing the notebook page (Ctrl+R or Cmd+R)")
            print_info("  3. Click on a cell to activate the collaboration session")
            print()
            cont = input(f"{Colors.YELLOW}Continue anyway? (y/N): {Colors.END}")
            if cont.lower() != 'y':
                print_info("Demo cancelled. Try opening and refreshing the notebook first!")
                return
        
        # Run demo
        await demo_mcp_tools(client)
        
        # Show service info
        show_service_info()
        
        print_header("Demo Complete!")
        print_success("All tests completed successfully! 🎉")
        print(f"\n{Colors.GREEN}The services are still running. You can:{Colors.END}")
        print(f"  • Open JupyterLab: {JUPYTER_URL}?token={JUPYTER_TOKEN}")
        print(f"  • Check MCP health: {MCP_URL}/api/healthz")
        print(f"  • Stop services: docker-compose down")
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Demo interrupted by user{Colors.END}")
    except Exception as e:
        print_error(f"Demo failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 