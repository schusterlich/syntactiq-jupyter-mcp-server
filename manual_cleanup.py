#!/usr/bin/env python3
"""
Manual Cleanup Script for Jupyter MCP Server Test Artifacts

This script provides manual cleanup functionality as a backup if the automatic
cleanup in the test suite fails or if you need to clean up artifacts manually.

Usage: python manual_cleanup.py [--notebooks-only] [--cells-only] [--dry-run]
"""

import asyncio
import argparse
import httpx
import sys
from pathlib import Path
from mcp_client import MCPClient

# Configuration
JUPYTER_URL = "http://localhost:8888"
MCP_URL = "http://localhost:4040" 
JUPYTER_TOKEN = "MY_TOKEN"

class Colors:
    """ANSI color codes for pretty output"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(message: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{message.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")

def print_info(message: str):
    """Print an info message"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def print_success(message: str):
    """Print a success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_warning(message: str):
    """Print a warning message"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def print_error(message: str):
    """Print an error message"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

async def clean_test_notebooks(dry_run: bool = False):
    """Clean up test notebooks created by the test suite"""
    print_info("Scanning for test notebooks...")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {}
            if JUPYTER_TOKEN:
                headers["Authorization"] = f"token {JUPYTER_TOKEN}"
            
            # Get all notebooks
            response = await client.get(f"{JUPYTER_URL}/api/contents", headers=headers)
            if response.status_code != 200:
                print_error(f"Failed to list notebooks: HTTP {response.status_code}")
                return False
            
            contents = response.json().get("content", [])
            test_notebooks = []
            
            # Find test notebooks (identify by naming patterns)
            test_patterns = [
                "test_notebook_",
                "switch_test_", 
                "test_",
                "_test_",
                "notebook_test"
            ]
            
            for item in contents:
                if item.get("type") == "notebook" and item.get("name", "").endswith(".ipynb"):
                    name = item.get("name", "")
                    path = item.get("path", "")
                    
                    # Skip the main test notebook
                    if name == "notebook.ipynb":
                        continue
                        
                    # Check if it matches test patterns
                    if any(pattern in name.lower() for pattern in test_patterns):
                        test_notebooks.append({
                            "name": name,
                            "path": path,
                            "size": item.get("size", 0)
                        })
            
            if not test_notebooks:
                print_success("No test notebooks found to clean up")
                return True
            
            print_info(f"Found {len(test_notebooks)} test notebooks:")
            for nb in test_notebooks:
                size_kb = nb["size"] / 1024 if nb["size"] else 0
                print(f"   📝 {nb['name']} ({size_kb:.1f}KB)")
            
            if dry_run:
                print_warning("DRY RUN: Would delete the above notebooks")
                return True
            
            # Ask for confirmation
            print(f"\n{Colors.YELLOW}Delete these {len(test_notebooks)} test notebooks? [y/N]: {Colors.END}", end="")
            confirm = input().strip().lower()
            
            if confirm != 'y':
                print_info("Cleanup cancelled by user")
                return True
            
            # Delete notebooks
            deleted_count = 0
            for nb in test_notebooks:
                try:
                    delete_response = await client.delete(
                        f"{JUPYTER_URL}/api/contents/{nb['path']}", 
                        headers=headers
                    )
                    
                    if delete_response.status_code in [204, 200]:
                        print_success(f"Deleted: {nb['name']}")
                        deleted_count += 1
                    else:
                        print_error(f"Failed to delete {nb['name']}: HTTP {delete_response.status_code}")
                        
                except Exception as e:
                    print_error(f"Error deleting {nb['name']}: {e}")
            
            print_success(f"Successfully deleted {deleted_count}/{len(test_notebooks)} test notebooks")
            return True
            
    except Exception as e:
        print_error(f"Failed to clean notebooks: {e}")
        return False

async def clean_excess_cells(target_count: int = None, dry_run: bool = False):
    """Clean up excess cells, optionally to a target count"""
    print_info("Connecting to MCP server for cell cleanup...")
    
    try:
        client = MCPClient(MCP_URL)
        
        # Get current cell count
        cells = await client.read_all_cells()
        current_count = len(cells)
        
        print_info(f"Current notebook has {current_count} cells")
        
        if target_count is None:
            # Interactive mode - ask user what to do
            print(f"\n{Colors.YELLOW}How many cells should remain? [current: {current_count}]: {Colors.END}", end="")
            user_input = input().strip()
            
            if not user_input:
                print_info("No target specified, keeping all cells")
                return True
                
            try:
                target_count = int(user_input)
            except ValueError:
                print_error("Invalid number entered")
                return False
        
        if target_count >= current_count:
            print_success("No excess cells to remove")
            return True
        
        cells_to_remove = current_count - target_count
        print_info(f"Will remove {cells_to_remove} cells (keeping {target_count})")
        
        if dry_run:
            print_warning(f"DRY RUN: Would delete {cells_to_remove} cells from the end")
            return True
        
        # Ask for confirmation
        print(f"\n{Colors.YELLOW}Remove {cells_to_remove} cells from the end? [y/N]: {Colors.END}", end="")
        confirm = input().strip().lower()
        
        if confirm != 'y':
            print_info("Cell cleanup cancelled by user")
            return True
        
        # Delete cells from the end
        for i in range(cells_to_remove):
            try:
                # Get current count (it decreases as we delete)
                current_cells = await client.read_all_cells()
                if len(current_cells) > target_count:
                    delete_index = len(current_cells) - 1
                    await client.call_tool("delete_cell", {"cell_index": delete_index})
                    print_success(f"Deleted cell {delete_index} ({i+1}/{cells_to_remove})")
                    await asyncio.sleep(0.1)  # Brief pause
                else:
                    break
            except Exception as e:
                print_error(f"Failed to delete cell {i+1}: {e}")
        
        # Verify final count
        final_cells = await client.read_all_cells()
        final_count = len(final_cells)
        
        if final_count == target_count:
            print_success(f"Cell cleanup completed: {final_count} cells remaining")
        else:
            print_warning(f"Cleanup partially successful: {final_count} cells remaining (target: {target_count})")
        
        return True
        
    except Exception as e:
        print_error(f"Failed to clean cells: {e}")
        return False

async def show_status():
    """Show current status of notebooks and cells"""
    print_info("Checking current workspace status...")
    
    try:
        # Check notebooks
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            headers = {}
            if JUPYTER_TOKEN:
                headers["Authorization"] = f"token {JUPYTER_TOKEN}"
            
            response = await http_client.get(f"{JUPYTER_URL}/api/contents", headers=headers)
            if response.status_code == 200:
                contents = response.json().get("content", [])
                notebooks = [item for item in contents if item.get("type") == "notebook"]
                print_info(f"Found {len(notebooks)} notebooks in workspace")
                
                for nb in notebooks:
                    name = nb.get("name", "unknown")
                    size_kb = nb.get("size", 0) / 1024
                    print(f"   📝 {name} ({size_kb:.1f}KB)")
            else:
                print_error(f"Failed to list notebooks: HTTP {response.status_code}")
        
        # Check cells in current notebook
        client = MCPClient(MCP_URL)
        cells = await client.read_all_cells()
        info = await client.get_notebook_info()
        
        current_notebook = info.get('room_id', 'unknown')
        print_info(f"Current notebook '{current_notebook}' has {len(cells)} cells")
        
        # Show cell types
        cell_types = {}
        for cell in cells:
            if isinstance(cell, dict) and 'content' in cell:
                content = str(cell['content'])
                if content.strip().startswith('#'):
                    cell_type = 'markdown'
                elif any(keyword in content for keyword in ['print(', 'import ', 'def ', 'class ']):
                    cell_type = 'code'
                else:
                    cell_type = 'other'
                cell_types[cell_type] = cell_types.get(cell_type, 0) + 1
        
        for cell_type, count in cell_types.items():
            print(f"   • {count} {cell_type} cells")
        
        return True
        
    except Exception as e:
        print_error(f"Failed to get status: {e}")
        return False

async def main():
    """Main cleanup function"""
    parser = argparse.ArgumentParser(description="Manual cleanup for Jupyter MCP test artifacts")
    parser.add_argument("--notebooks-only", action="store_true", help="Only clean up test notebooks")
    parser.add_argument("--cells-only", action="store_true", help="Only clean up excess cells")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be cleaned without doing it")
    parser.add_argument("--target-cells", type=int, help="Target number of cells to keep")
    parser.add_argument("--status", action="store_true", help="Show current workspace status")
    
    args = parser.parse_args()
    
    print_header("Manual Cleanup for Jupyter MCP Test Artifacts")
    
    if args.status:
        await show_status()
        return
    
    success = True
    
    if args.dry_run:
        print_warning("DRY RUN MODE: No actual changes will be made")
    
    if not args.cells_only:
        print_info("🧹 Cleaning up test notebooks...")
        success &= await clean_test_notebooks(dry_run=args.dry_run)
    
    if not args.notebooks_only:
        print_info("🧹 Cleaning up excess cells...")
        success &= await clean_excess_cells(target_count=args.target_cells, dry_run=args.dry_run)
    
    if success:
        print_success("🎉 Manual cleanup completed successfully!")
    else:
        print_error("⚠️ Some cleanup operations failed")
    
    print_info("\n💡 Usage examples:")
    print("   python manual_cleanup.py --status                    # Show current status")
    print("   python manual_cleanup.py --dry-run                   # Preview cleanup")
    print("   python manual_cleanup.py --notebooks-only            # Only clean notebooks")  
    print("   python manual_cleanup.py --cells-only --target-cells 5  # Keep only 5 cells")

if __name__ == "__main__":
    asyncio.run(main()) 