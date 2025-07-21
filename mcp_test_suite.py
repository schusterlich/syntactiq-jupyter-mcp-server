#!/usr/bin/env python3
"""
Comprehensive Jupyter MCP Server Test Suite

This script provides automated testing for ALL MCP tools with multiple test cases per tool.
Tests are organized by tool category with detailed validation and error handling.

Usage: python test_mcp_demo.py
"""

import asyncio
import httpx
import json
import subprocess
import time
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path
import random
import string

# Import our MCP client
from mcp_client import MCPClient

# Configuration
JUPYTER_URL = "http://localhost:8888"
MCP_URL = "http://localhost:4040"
JUPYTER_TOKEN = "MY_TOKEN"
TIMEOUT_SECONDS = 300

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

class TestResults:
    """Track test results across all test categories"""
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.errors = []
    
    def add_result(self, test_name: str, passed: bool, error: str = None):
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            print_success(f"✅ {test_name}")
        else:
            self.failed_tests += 1
            print_error(f"❌ {test_name}")
            if error:
                self.errors.append(f"{test_name}: {error}")
                print_error(f"   Error: {error}")
    
    def print_summary(self):
        print_header("Test Summary")
        success_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        
        print(f"Total Tests: {self.total_tests}")
        print(f"{Colors.GREEN}Passed: {self.passed_tests}{Colors.END}")
        print(f"{Colors.RED}Failed: {self.failed_tests}{Colors.END}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if self.errors:
            print("\n❌ Failed Tests:")
            for error in self.errors:
                print(f"   • {error}")
        
        return self.failed_tests == 0

def print_header(message: str):
    """Print a formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message.center(80)}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}\n")

def print_category(category: str):
    """Print a test category header"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}📋 {category}{Colors.END}")
    print(f"{Colors.CYAN}{'─' * (len(category) + 4)}{Colors.END}")

def print_test(test_name: str):
    """Print a test case name"""
    print(f"{Colors.BLUE}🔸 {test_name}...{Colors.END}", end=" ")

def print_success(message: str):
    """Print a success message"""
    print(f"{Colors.GREEN}{message}{Colors.END}")

def print_error(message: str):
    """Print an error message"""  
    print(f"{Colors.RED}{message}{Colors.END}")

def print_info(message: str):
    """Print an info message"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def generate_test_id() -> str:
    """Generate a unique test identifier"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

async def start_services():
    """Start docker-compose services"""
    print_category("Service Startup")
    
    try:
        subprocess.run(["docker-compose", "down"], capture_output=True, check=False)
        result = subprocess.run(["docker-compose", "up", "-d"], capture_output=True, text=True, check=True)
        print_success("Docker services started")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to start services: {e}")
        return False

async def wait_for_services():
    """Wait for all services to be healthy"""
    print_category("Service Health Checks")
    
    services = [
        ("JupyterLab", f"{JUPYTER_URL}/api"),
        ("MCP Server", f"{MCP_URL}/api/healthz")
    ]
    
    for service_name, health_url in services:
        print_test(f"Waiting for {service_name}")
        
        start_time = time.time()
        while time.time() - start_time < TIMEOUT_SECONDS:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(health_url)
                    if response.status_code == 200:
                        print_success(f"{service_name} healthy")
                        break
            except:
                pass
            await asyncio.sleep(2)
        else:
            print_error(f"{service_name} failed to start")
            return False
    
    return True

async def test_notebook_info_tools(client: MCPClient, results: TestResults):
    """Test notebook information and metadata tools"""
    print_category("Notebook Information Tools")
    
    # Test 1: Basic notebook info retrieval
    print_test("get_notebook_info - Basic retrieval")
    try:
        info = await client.get_notebook_info()
        assert isinstance(info, dict), "Should return dict"
        assert 'room_id' in info, "Should have room_id"
        results.add_result("get_notebook_info - Basic", True)
    except Exception as e:
        results.add_result("get_notebook_info - Basic", False, str(e))
    
    # Test 2: Info consistency across calls  
    print_test("get_notebook_info - Consistency check")
    try:
        info1 = await client.get_notebook_info()
        await asyncio.sleep(1)
        info2 = await client.get_notebook_info()
        assert info1.get('room_id') == info2.get('room_id'), "Room ID should be consistent"
        results.add_result("get_notebook_info - Consistency", True)
    except Exception as e:
        results.add_result("get_notebook_info - Consistency", False, str(e))

async def test_cell_reading_tools(client: MCPClient, results: TestResults):
    """Test cell reading and content retrieval tools"""
    print_category("Cell Reading Tools")
    
    # Test 1: Read all cells
    print_test("read_all_cells - Basic retrieval")
    try:
        cells = await client.read_all_cells()
        assert isinstance(cells, list), "Should return list"
        assert len(cells) >= 0, "Should have non-negative length"
        results.add_result("read_all_cells - Basic", True)
    except Exception as e:
        results.add_result("read_all_cells - Basic", False, str(e))
    
    # Test 2: Read all cells structure validation
    print_test("read_all_cells - Structure validation")
    try:
        cells = await client.read_all_cells()
        if cells:
            first_cell = cells[0]
            assert isinstance(first_cell, dict), "Each cell should be dict"
            assert 'type' in first_cell, "Cell should have type"
            assert 'source' in first_cell, "Cell should have source"
        results.add_result("read_all_cells - Structure", True)
    except Exception as e:
        results.add_result("read_all_cells - Structure", False, str(e))
    
    # Test 3: Read specific cell (if cells exist)
    print_test("read_cell - Specific cell retrieval")
    try:
        cells = await client.read_all_cells()
        if cells:
            cell = await client.read_cell(0)
            assert isinstance(cell, dict), "Should return dict"
            assert cell.get('type') == cells[0].get('type'), "Should match first cell type"
        results.add_result("read_cell - Specific", True)
    except Exception as e:
        results.add_result("read_cell - Specific", False, str(e))

async def test_markdown_cell_tools(client: MCPClient, results: TestResults):
    """Test markdown cell creation and manipulation tools"""
    print_category("Markdown Cell Tools")
    
    test_id = generate_test_id()
    
    # Test 1: Append markdown cell
    print_test("append_markdown_cell - Basic addition")
    try:
        markdown_content = f"# Test Markdown Cell {test_id}\n\nThis is a **test** markdown cell created by automated testing."
        result = await client.append_markdown_cell(markdown_content)
        assert isinstance(result, str), "Should return string result"
        results.add_result("append_markdown_cell - Basic", True)
    except Exception as e:
        results.add_result("append_markdown_cell - Basic", False, str(e))
    
    # Test 2: Append markdown with special characters
    print_test("append_markdown_cell - Special characters")
    try:
        special_content = f"## Special Test {test_id}\n\n- List item with `code`\n- **Bold** and *italic*\n- [Link](https://example.com)\n\n```python\nprint('hello')\n```"
        result = await client.append_markdown_cell(special_content)
        results.add_result("append_markdown_cell - Special chars", True)
    except Exception as e:
        results.add_result("append_markdown_cell - Special chars", False, str(e))
    
    # Test 3: Insert markdown at specific position
    print_test("insert_markdown_cell - Positional insertion")
    try:
        cells_before = await client.read_all_cells()
        insert_content = f"### Inserted Test {test_id}\n\nThis cell was inserted at position 1."
        result = await client.insert_markdown_cell(1, insert_content)
        cells_after = await client.read_all_cells()
        assert len(cells_after) > len(cells_before), "Should have more cells after insertion"
        results.add_result("insert_markdown_cell - Position", True)
    except Exception as e:
        results.add_result("insert_markdown_cell - Position", False, str(e))

async def test_code_cell_tools(client: MCPClient, results: TestResults):
    """Test code cell creation and execution tools"""
    print_category("Code Cell Tools")
    
    test_id = generate_test_id()
    
    # Test 1: Append and execute simple code
    print_test("append_execute_code_cell - Simple execution")
    try:
        simple_code = f"# Test {test_id}\nprint('Hello from test {test_id}')\nresult = 2 + 2\nprint(f'2 + 2 = {{result}}')"
        outputs = await client.append_execute_code_cell(simple_code)
        assert isinstance(outputs, list), "Should return list of outputs"
        results.add_result("append_execute_code_cell - Simple", True)
    except Exception as e:
        results.add_result("append_execute_code_cell - Simple", False, str(e))
    
    # Test 2: Code with imports and computation
    print_test("append_execute_code_cell - Complex computation")
    try:
        complex_code = f"""
import math
import datetime

# Test computation {test_id}
numbers = [1, 2, 3, 4, 5]
squared = [x**2 for x in numbers]
print(f"Original: {{numbers}}")
print(f"Squared: {{squared}}")
print(f"Sum of squares: {{sum(squared)}}")
print(f"Square root of 16: {{math.sqrt(16)}}")
print(f"Current time: {{datetime.datetime.now().strftime('%H:%M:%S')}}")
"""
        outputs = await client.append_execute_code_cell(complex_code)
        assert len(outputs) > 0, "Should have execution outputs"
        results.add_result("append_execute_code_cell - Complex", True)
    except Exception as e:
        results.add_result("append_execute_code_cell - Complex", False, str(e))
    
    # Test 3: Insert and execute code at position
    print_test("insert_execute_code_cell - Positional execution")
    try:
        cells_before = await client.read_all_cells()
        insert_code = f"# Inserted code test {test_id}\nfor i in range(3):\n    print(f'Loop {{i}}: test {test_id}')"
        outputs = await client.insert_execute_code_cell(2, insert_code)
        assert isinstance(outputs, list), "Should return execution outputs"
        cells_after = await client.read_all_cells()
        assert len(cells_after) > len(cells_before), "Should have more cells"
        results.add_result("insert_execute_code_cell - Position", True)
    except Exception as e:
        results.add_result("insert_execute_code_cell - Position", False, str(e))

async def test_cell_execution_tools(client: MCPClient, results: TestResults):
    """Test various cell execution methods"""
    print_category("Cell Execution Tools")
    
    test_id = generate_test_id()
    
    # First, create a test cell to execute
    test_code = f"# Execution test {test_id}\nimport time\nprint('Starting execution test')\ntime.sleep(1)\nprint('Test completed')\nresult = 42\nprint(f'Final result: {{result}}')"
    await client.append_execute_code_cell(test_code)
    
    # Get the index of the last cell
    cells = await client.read_all_cells()
    last_index = len(cells) - 1
    
    # Test 1: Execute with progress monitoring
    print_test("execute_cell_with_progress - Progress tracking")
    try:
        outputs = await client.execute_with_progress(last_index)
        assert isinstance(outputs, list), "Should return outputs list"
        results.add_result("execute_cell_with_progress - Progress", True)
    except Exception as e:
        results.add_result("execute_cell_with_progress - Progress", False, str(e))
    
    # Test 2: Execute with simple timeout
    print_test("execute_cell_simple_timeout - Timeout handling")
    try:
        # Create a quick execution test
        quick_code = f"print('Quick test {test_id}')"
        await client.append_execute_code_cell(quick_code)
        cells = await client.read_all_cells()
        quick_index = len(cells) - 1
        
        outputs = await client.call_tool("execute_cell_simple_timeout", {
            "cell_index": quick_index,
            "timeout_seconds": 30
        })
        results.add_result("execute_cell_simple_timeout - Basic", True)
    except Exception as e:
        results.add_result("execute_cell_simple_timeout - Basic", False, str(e))

async def test_cell_manipulation_tools(client: MCPClient, results: TestResults):
    """Test cell editing and deletion tools"""
    print_category("Cell Manipulation Tools")
    
    test_id = generate_test_id()
    
    # First create a test cell to manipulate
    original_content = f"# Original content {test_id}\nprint('This will be overwritten')"
    await client.append_markdown_cell(original_content)
    cells = await client.read_all_cells()
    target_index = len(cells) - 1
    
    # Test 1: Overwrite cell source
    print_test("overwrite_cell_source - Content replacement")
    try:
        new_content = f"# Updated content {test_id}\nprint('Content has been overwritten')\nprint('Successfully updated!')"
        result = await client.call_tool("overwrite_cell_source", {
            "cell_index": target_index,
            "cell_source": new_content
        })
        
        # Verify the change
        updated_cells = await client.read_all_cells()
        updated_cell = updated_cells[target_index]
        assert new_content in str(updated_cell.get('source', '')), "Content should be updated"
        results.add_result("overwrite_cell_source - Replace", True)
    except Exception as e:
        results.add_result("overwrite_cell_source - Replace", False, str(e))
    
    # Test 2: Delete cell
    print_test("delete_cell - Cell removal")
    try:
        cells_before = await client.read_all_cells()
        await client.call_tool("delete_cell", {"cell_index": target_index})
        cells_after = await client.read_all_cells()
        assert len(cells_after) < len(cells_before), "Should have fewer cells after deletion"
        results.add_result("delete_cell - Remove", True)
    except Exception as e:
        results.add_result("delete_cell - Remove", False, str(e))

async def test_notebook_management_tools(client: MCPClient, results: TestResults):
    """Test notebook creation and management tools"""
    print_category("Notebook Management Tools")
    
    test_id = generate_test_id()
    
    # Test 1: List existing notebooks
    print_test("list_notebooks - Workspace discovery")
    try:
        notebooks_info = await client.list_notebooks()
        assert isinstance(notebooks_info, dict), "Should return dict"
        assert 'total_found' in notebooks_info, "Should have total count"
        assert isinstance(notebooks_info.get('notebooks', []), list), "Should have notebooks list"
        results.add_result("list_notebooks - Discovery", True)
    except Exception as e:
        results.add_result("list_notebooks - Discovery", False, str(e))
    
    # Test 2: Create new notebook
    print_test("create_notebook - New notebook creation")
    try:
        new_notebook_path = f"test_notebook_{test_id}.ipynb"
        initial_content = f"# Test Notebook {test_id}\n\nThis notebook was created by automated testing.\n\n## Features\n- Automatic creation\n- Session setup\n- Content initialization"
        
        result = await client.create_notebook(new_notebook_path, initial_content, switch_to_notebook=False)
        assert isinstance(result, str), "Should return result string"
        results.add_result("create_notebook - Creation", True)
    except Exception as e:
        results.add_result("create_notebook - Creation", False, str(e))
    
    # Test 3: Create and switch to notebook
    print_test("create_notebook - Create and switch context")
    try:
        switch_notebook_path = f"switch_test_{test_id}.ipynb"
        switch_content = f"# Switch Test {test_id}\n\nThis tests automatic context switching."
        
        result = await client.create_notebook(switch_notebook_path, switch_content, switch_to_notebook=True)
        
        # Verify the switch
        info = await client.get_notebook_info()
        current_room = info.get('room_id', '') if isinstance(info, dict) else str(info)
        assert switch_notebook_path in current_room, "Should have switched to new notebook"
        results.add_result("create_notebook - Switch", True)
    except Exception as e:
        results.add_result("create_notebook - Switch", False, str(e))

async def test_workspace_tools(client: MCPClient, results: TestResults):
    """Test workspace and session management tools"""
    print_category("Workspace Management Tools")
    
    # Test 1: List open notebooks
    print_test("list_open_notebooks - Open session tracking")
    try:
        open_info = await client.list_open_notebooks()
        assert isinstance(open_info, dict), "Should return dict"
        assert 'total_open' in open_info, "Should have total count"
        results.add_result("list_open_notebooks - Tracking", True)
    except Exception as e:
        results.add_result("list_open_notebooks - Tracking", False, str(e))
    
    # Test 2: Prepare notebook (one-stop tool)
    print_test("prepare_notebook - One-stop preparation")
    try:
        # Get available notebooks first
        notebooks_info = await client.list_notebooks()
        available = notebooks_info.get('notebooks', [])
        
        if available:
            target_notebook = available[0].get('path', 'notebook.ipynb')
            result = await client.prepare_notebook(target_notebook)
            assert isinstance(result, str), "Should return preparation result"
            assert 'http' in result.lower(), "Should contain URL"
            results.add_result("prepare_notebook - Preparation", True)
        else:
            results.add_result("prepare_notebook - Preparation", True, "No notebooks to test with")
    except Exception as e:
        results.add_result("prepare_notebook - Preparation", False, str(e))

async def setup_test_environment():
    """Setup initial test environment"""
    print_category("Test Environment Setup")
    
    # Ensure notebooks directory exists
    notebooks_dir = Path("notebooks")
    notebooks_dir.mkdir(exist_ok=True)
    
    # Create a basic test notebook if none exists
    test_notebook = notebooks_dir / "notebook.ipynb"
    if not test_notebook.exists():
        basic_notebook = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["# Test Notebook\n\nThis notebook is used for MCP testing."]
                }
            ],
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                "language_info": {"name": "python", "version": "3.10.0"}
            },
            "nbformat": 4,
            "nbformat_minor": 4
        }
        
        with open(test_notebook, 'w') as f:
            json.dump(basic_notebook, f, indent=2)
        
        print_success("Created basic test notebook")

async def wait_for_notebook_session(client: MCPClient):
    """Wait for notebook collaboration session to be ready"""
    print_category("Notebook Session Setup")
    
    print_info("Please open notebook.ipynb in JupyterLab to establish collaboration session")
    print_info(f"URL: {JUPYTER_URL}?token={JUPYTER_TOKEN}")
    print_info("Press Enter after opening the notebook...")
    input()
    
    # Wait for session to be established
    print_test("Waiting for collaboration session")
    for attempt in range(10):
        try:
            info = await client.get_notebook_info()
            room_id = info.get('room_id') if isinstance(info, dict) else str(info)
            
            if room_id and room_id not in ['None', 'Unknown', '']:
                print_success(f"Session established: {room_id}")
                return True
        except:
            pass
        
        await asyncio.sleep(3)
    
    print_error("Could not establish notebook session")
    return False

async def main():
    """Main test execution function"""
    print_header("Comprehensive MCP Server Test Suite")
    
    results = TestResults()
    
    # Setup test environment
    await setup_test_environment()
    
    # Start services
    if not await start_services():
        print_error("Failed to start services")
        return False
    
    await asyncio.sleep(15)  # Wait for startup
    
    # Check service health
    if not await wait_for_services():
        print_error("Services failed health checks")
        return False
    
    # Initialize client
    client = MCPClient(MCP_URL)
    
    # Wait for notebook session
    if not await wait_for_notebook_session(client):
        print_error("Failed to establish notebook session")
        return False
    
    # Run comprehensive test suites
    try:
        await test_notebook_info_tools(client, results)
        await test_cell_reading_tools(client, results)
        await test_markdown_cell_tools(client, results)
        await test_code_cell_tools(client, results)
        await test_cell_execution_tools(client, results)
        await test_cell_manipulation_tools(client, results)
        await test_notebook_management_tools(client, results)
        await test_workspace_tools(client, results)
        
    except Exception as e:
        print_error(f"Test suite failed: {e}")
        return False
    
    # Print final results
    success = results.print_summary()
    
    if success:
        print_header("🎉 All Tests Passed!")
        print_info("Your MCP server is fully functional with all tools working correctly!")
    else:
        print_header("⚠️ Some Tests Failed")
        print_info("Check the errors above and fix any issues before production use.")
    
    print_info("\nService Management:")
    print_info("• Stop services: docker-compose down")
    print_info("• View logs: docker-compose logs -f")
    print_info(f"• JupyterLab: {JUPYTER_URL}?token={JUPYTER_TOKEN}")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 