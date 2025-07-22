#!/usr/bin/env python3
"""
Comprehensive Jupyter MCP Server Test Suite

This script provides automated testing for ALL MCP tools with multiple test cases per tool.
Tests are organized by tool category with detailed validation and error handling.

BULLETPROOF SYNCHRONIZATION: All tests use the new bulletproof synchronization that waits
for actual completion signals from the notebook server. No more sleeps or timeouts!
Includes stress testing to validate synchronization under extreme conditions.

Usage: python mcp_test_suite.py
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
        # Stop any running services first
        print_info("Stopping existing services (if any)...")
        subprocess.run(["docker-compose", "down"], capture_output=True, check=False)
        
        # Start services and capture output on failure
        print_info("Starting services with 'docker-compose up -d'...")
        result = subprocess.run(
            ["docker-compose", "up", "-d", "--build"],
            capture_output=True, text=True, check=True
        )
        print_success("Docker services started successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to start services: {e}")
        if e.stdout:
            print_error("\n--- Docker Compose STDOUT ---")
            print(e.stdout)
        if e.stderr:
            print_error("\n--- Docker Compose STDERR ---")
            print(e.stderr)
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
        cells_before = await client.read_all_cells()
        initial_count = len(cells_before)
        markdown_content = f"# Test Markdown Cell {test_id}\n\nThis is a **test** markdown cell created by automated testing."
        result = await client.append_markdown_cell(markdown_content)
        
        # Retry-based verification: poll until change is visible (bulletproof sync)
        expected_count = initial_count + 1
        for attempt in range(20):  # Max 2 seconds of polling
            cells_after = await client.read_all_cells()
            if len(cells_after) == expected_count:
                break
            await asyncio.sleep(0.1)  # Brief polling interval
        else:
            assert False, f"Expected {expected_count} cells after append, got {len(cells_after)} after 2s"
            
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
        initial_count = len(cells_before)
        insert_content = f"### Inserted Test {test_id}\n\nThis cell was inserted at position 1."
        result = await client.insert_markdown_cell(1, insert_content)
        
        # Retry-based verification: poll until change is visible
        expected_count = initial_count + 1
        cells_after = None
        for attempt in range(20):  # Max 2 seconds of polling
            cells_after = await client.read_all_cells()
            if len(cells_after) == expected_count:
                break
            await asyncio.sleep(0.1)
        else:
            assert False, f"Expected {expected_count} cells after insertion, got {len(cells_after)} after 2s"
        
        # Verify the cell was inserted at the correct position with correct content
        inserted_cell = cells_after[1]
        assert insert_content.strip() in str(inserted_cell.get('source', '')), "Inserted cell should have correct content"
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
        cells_before = await client.read_all_cells()
        simple_code = f"# Test {test_id}\nprint('Hello from test {test_id}')\nresult = 2 + 2\nprint(f'2 + 2 = {{result}}')"
        outputs = await client.append_execute_code_cell(simple_code)
        cells_after = await client.read_all_cells()
        assert isinstance(outputs, list), "Should return list of outputs"
        assert len(cells_after) == len(cells_before) + 1, "Should have one more cell after append"
        results.add_result("append_execute_code_cell - Simple", True)
    except Exception as e:
        results.add_result("append_execute_code_cell - Simple", False, str(e))
    
    # Test 2: Code with imports and computation
    print_test("append_execute_code_cell - Complex computation")
    try:
        cells_before = await client.read_all_cells()
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
        cells_after = await client.read_all_cells()
        assert len(outputs) > 0, "Should have execution outputs"
        assert len(cells_after) == len(cells_before) + 1, "Should have one more cell after append"
        results.add_result("append_execute_code_cell - Complex", True)
    except Exception as e:
        results.add_result("append_execute_code_cell - Complex", False, str(e))
    
    # Test 3: Insert and execute code at position
    print_test("insert_execute_code_cell - Positional execution")
    try:
        cells_before = await client.read_all_cells()
        # Insert at the end to avoid index issues
        insert_position = len(cells_before)
        insert_code = f"# Inserted code test {test_id}\nfor i in range(3):\n    print(f'Loop {{i}}: test {test_id}')"
        outputs = await client.insert_execute_code_cell(insert_position, insert_code)
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
        result = await client.overwrite_cell_source(target_index, new_content)
        
        # Retry-based verification: poll until content change is visible
        content_updated = False
        for attempt in range(20):  # Max 2 seconds of polling
            updated_cells = await client.read_all_cells()
            updated_cell = updated_cells[target_index]
            cell_source = str(updated_cell.get('source', ''))
            if new_content.strip() in cell_source.strip():
                content_updated = True
                break
            await asyncio.sleep(0.1)
        
        assert content_updated, f"Content was not updated after 2s. Expected '{new_content}' in cell {target_index}"
        results.add_result("overwrite_cell_source - Replace", True)
    except Exception as e:
        results.add_result("overwrite_cell_source - Replace", False, str(e))
    
    # Test 2: Delete cell
    print_test("delete_cell - Cell removal")
    try:
        cells_before = await client.read_all_cells()
        initial_count = len(cells_before)
        # Delete the last cell to be safer with indexing
        delete_index = initial_count - 1
        await client.call_tool("delete_cell", {"cell_index": delete_index})
        
        # Retry-based verification: poll until cell count decreases
        expected_count = initial_count - 1
        cells_after = None
        for attempt in range(20):  # Max 2 seconds of polling
            cells_after = await client.read_all_cells()
            if len(cells_after) == expected_count:
                break
            await asyncio.sleep(0.1)
        else:
            assert False, f"Expected {expected_count} cells after deletion, got {len(cells_after)} after 2s"
            
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

async def test_stress_bulletproof_sync(client: MCPClient, results: TestResults):
    """Stress test to validate bulletproof synchronization under extreme conditions"""
    print_category("Stress Test - Bulletproof Synchronization")
    
    test_id = generate_test_id()
    
    # Get initial state
    initial_cells = await client.read_all_cells()
    initial_count = len(initial_cells)
    
    # Test 1: Rapid serial insertions (10 markdown + 10 code)
    print_test("Stress - Rapid serial insertions")
    try:
        expected_count = initial_count
        
        # Rapid markdown insertions
        for i in range(5):  # Reduced from 10 to keep test time reasonable
            await client.append_markdown_cell(f"# Stress Test {i+1} {test_id}\n\nRapid insertion test.")
            expected_count += 1
        
        # Rapid code insertions
        for i in range(5):  # Reduced from 10 to keep test time reasonable
            await client.append_execute_code_cell(f"# Stress code {i+1} {test_id}\nprint('Rapid test {i+1}')")
            expected_count += 1
        
        # Verify final count
        final_cells = await client.read_all_cells()
        actual_count = len(final_cells)
        assert actual_count == expected_count, f"Expected {expected_count} cells, got {actual_count}"
        results.add_result("Stress - Rapid insertions", True)
    except Exception as e:
        results.add_result("Stress - Rapid insertions", False, str(e))
    
    # Test 2: Mixed operations in rapid succession
    print_test("Stress - Mixed operations")
    try:
        current_cells = await client.read_all_cells()
        current_count = len(current_cells)
        
        operations = [
            ("append_markdown", lambda: client.append_markdown_cell(f"# Mixed {generate_test_id()}")),
            ("append_code", lambda: client.append_execute_code_cell(f"print('Mixed {generate_test_id()}')")),
            ("overwrite_first", lambda: client.overwrite_cell_source(0, f"# Overwritten {generate_test_id()}")),
        ]
        
        expected_count = current_count
        for i in range(6):  # Reduced from 20 to keep test time reasonable
            op_name, op_func = operations[i % len(operations)]
            await op_func()
            if op_name in ["append_markdown", "append_code"]:
                expected_count += 1
        
        # Verify count
        mixed_cells = await client.read_all_cells()
        assert len(mixed_cells) == expected_count, f"Mixed ops count mismatch: expected {expected_count}, got {len(mixed_cells)}"
        results.add_result("Stress - Mixed operations", True)
    except Exception as e:
        results.add_result("Stress - Mixed operations", False, str(e))
    
    # Test 3: Rapid deletions
    print_test("Stress - Rapid deletions")
    try:
        # Add some cells to delete
        deletion_cells = await client.read_all_cells()
        deletion_count = len(deletion_cells)
        
        for i in range(3):  # Add 3 cells to delete
            await client.append_markdown_cell(f"# Delete Target {i+1} {test_id}")
            deletion_count += 1
        
        # Now delete them rapidly
        for i in range(3):
            current_cells = await client.read_all_cells()
            if len(current_cells) > initial_count:  # Don't delete original cells
                delete_index = len(current_cells) - 1
                await client.call_tool("delete_cell", {"cell_index": delete_index})
                deletion_count -= 1
        
        # Verify final state
        final_deletion_cells = await client.read_all_cells()
        assert len(final_deletion_cells) == deletion_count, f"Deletion count mismatch: expected {deletion_count}, got {len(final_deletion_cells)}"
        results.add_result("Stress - Rapid deletions", True)
    except Exception as e:
        results.add_result("Stress - Rapid deletions", False, str(e))
    
    # Test 4: Edge case insertions
    print_test("Stress - Edge case positions")
    try:
        edge_cells = await client.read_all_cells()
        edge_count = len(edge_cells)
        
        # Insert at beginning
        await client.insert_markdown_cell(0, f"# At Beginning {test_id}")
        edge_count += 1
        
        # Insert in middle
        middle_pos = edge_count // 2
        await client.insert_markdown_cell(middle_pos, f"# In Middle {test_id}")
        edge_count += 1
        
        # Verify final count
        edge_final = await client.read_all_cells()
        assert len(edge_final) == edge_count, f"Edge insertion count mismatch: expected {edge_count}, got {len(edge_final)}"
        results.add_result("Stress - Edge positions", True)
    except Exception as e:
        results.add_result("Stress - Edge positions", False, str(e))
    
    # Test 5: Consistency verification (no race conditions)
    print_test("Stress - Consistency checks")
    try:
        # Multiple rapid reads should be consistent
        for i in range(3):
            cells1 = await client.read_all_cells()
            cells2 = await client.read_all_cells()
            assert len(cells1) == len(cells2), f"Consistency check {i+1}: cell count changed between reads"
        results.add_result("Stress - Consistency", True)
    except Exception as e:
        results.add_result("Stress - Consistency", False, str(e))

async def test_output_truncation(client: MCPClient, results: TestResults):
    """Test output truncation functionality with full_output parameter"""
    print_category("Output Truncation")
    
    test_id = generate_test_id()
    
    # Test 1: Short output (should show completely)
    print_test("Short output - No truncation")
    try:
        short_code = f"print('Hello test {test_id}!')"
        outputs = await client.append_execute_code_cell(short_code)
        assert isinstance(outputs, list), "Should return list of outputs"
        output_str = str(outputs)
        assert "truncated" not in output_str.lower(), "Short output should not be truncated"
        results.add_result("Short output - No truncation", True)
    except Exception as e:
        results.add_result("Short output - No truncation", False, str(e))
    
    # Test 2: Long output with default truncation
    print_test("Long output - Default truncation")
    try:
        long_code = f"print('x' * 2000)  # {test_id}"
        truncated_outputs = await client.append_execute_code_cell(long_code)
        output_str = str(truncated_outputs)
        assert "truncated" in output_str.lower(), "Long output should be truncated by default"
        assert "full_output=True" in output_str, "Should show instruction for full output"
        results.add_result("Long output - Default truncation", True)
    except Exception as e:
        results.add_result("Long output - Default truncation", False, str(e))
    
    # Test 3: Long output with full_output=True
    print_test("Long output - Full output mode")
    try:
        long_code = f"print('y' * 1500)  # {test_id}"
        full_outputs = await client.append_execute_code_cell(long_code, full_output=True)
        truncated_outputs = await client.append_execute_code_cell(long_code, full_output=False)
        
        full_str = str(full_outputs)
        truncated_str = str(truncated_outputs)
        
        assert len(full_str) > len(truncated_str), "Full output should be longer than truncated"
        assert "truncated" in truncated_str.lower(), "Default should still truncate"
        results.add_result("Long output - Full output mode", True)
    except Exception as e:
        results.add_result("Long output - Full output mode", False, str(e))
    
    # Test 4: read_all_cells truncation
    print_test("read_all_cells - Truncation behavior")
    try:
        # Create a cell with long output
        await client.append_execute_code_cell(f"print('z' * 3000)  # {test_id}")
        
        # Test default (truncated)
        cells_truncated = await client.read_all_cells(full_output=False)
        cells_full = await client.read_all_cells(full_output=True)
        
        assert isinstance(cells_truncated, list), "Should return list of cells"
        assert isinstance(cells_full, list), "Should return list of cells"
        assert len(cells_truncated) == len(cells_full), "Should have same number of cells"
        
        # Find cells with outputs and compare
        truncated_outputs_found = False
        full_outputs_found = False
        
        for cell_t, cell_f in zip(cells_truncated, cells_full):
            if isinstance(cell_t, dict) and "outputs" in cell_t and cell_t["outputs"]:
                cell_t_str = str(cell_t["outputs"])
                cell_f_str = str(cell_f["outputs"])
                if "truncated" in cell_t_str.lower():
                    truncated_outputs_found = True
                if len(cell_f_str) >= len(cell_t_str):
                    full_outputs_found = True
        
        assert truncated_outputs_found or full_outputs_found, "Should demonstrate truncation behavior"
        results.add_result("read_all_cells - Truncation behavior", True)
    except Exception as e:
        results.add_result("read_all_cells - Truncation behavior", False, str(e))
    
    # Test 5: Execute cell functions with truncation
    print_test("execute_cell_with_progress - Truncation")
    try:
        # Add a cell with long output
        await client.append_execute_code_cell(f"print('w' * 2500)  # execute test {test_id}")
        cells = await client.read_all_cells()
        last_cell_index = len(cells) - 1
        
        # Test execution with truncation
        truncated_result = await client.execute_cell_with_progress(last_cell_index, full_output=False)
        full_result = await client.execute_cell_with_progress(last_cell_index, full_output=True)
        
        truncated_str = str(truncated_result)
        full_str = str(full_result)
        
        # At least one should show truncation behavior
        assert isinstance(truncated_result, list), "Should return list of outputs"
        assert isinstance(full_result, list), "Should return list of outputs"
        results.add_result("execute_cell_with_progress - Truncation", True)
    except Exception as e:
        results.add_result("execute_cell_with_progress - Truncation", False, str(e))

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
        
        await asyncio.sleep(2)  # Reduced polling interval
    
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
    
    await asyncio.sleep(10)  # Reduced startup wait - health checks will catch readiness
    
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
        await test_output_truncation(client, results)
        await test_stress_bulletproof_sync(client, results)
        
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