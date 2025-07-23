# Jupyter MCP Server API Documentation

**Version: 1.0** | **Last Updated: 2024**

This documentation covers all available MCP (Model Context Protocol) tools for interacting with Jupyter notebooks programmatically. Perfect for building LLM agents and automation platforms.

## 📚 Table of Contents

- [Quick Start](#quick-start)
- [Authentication & Connection](#authentication--connection)
- [Core Concepts](#core-concepts)
- [API Reference](#api-reference)
  - [Diagnostic Tools](#diagnostic-tools)
  - [Cell Reading Tools](#cell-reading-tools)
  - [Cell Manipulation Tools](#cell-manipulation-tools)
  - [Code Execution Tools](#code-execution-tools)
  - [Notebook Management Tools](#notebook-management-tools)
  - [Workspace Management Tools](#workspace-management-tools)
- [Error & Warning Detection](#error--warning-detection)
- [Response Formats](#response-formats)
- [Usage Patterns](#usage-patterns)
- [Examples](#examples)

---

## 🚀 Quick Start

```python
from mcp_client import MCPClient

# Initialize client
client = MCPClient("http://localhost:4040")

# Get notebook info
info = await client.get_notebook_info()
print(f"Connected to: {info['room_id']}")

# Execute code with error detection
result = await client.append_execute_code_cell("print('Hello World!')")
if client.has_error(result):
    print(f"Error: {client.get_error_info(result)}")
else:
    print(f"Output: {result['output']}")
```

---

## 🔐 Authentication & Connection

### Base URL
- **Default**: `http://localhost:4040`
- **Production**: Use your deployed MCP server URL

### HTTP Transport
- **Protocol**: HTTP POST with JSON-RPC 2.0
- **Endpoint**: `/mcp`
- **Format**: Server-Sent Events (SSE) or direct JSON

### Environment Setup
```bash
# Start services
docker-compose up -d

# Verify health
curl http://localhost:4040/api/healthz
curl http://localhost:8888/api
```

---

## 🧩 Core Concepts

### Cell Objects
All cell operations return standardized cell objects:

```python
{
    "cell_index": 0,           # 0-based position in notebook
    "cell_id": "cell-abc123",  # Unique cell identifier
    "content": "print('hi')",  # Cell source code/markdown
    "output": ["Hello!"],      # Execution outputs (list of strings)
    "images": [                # Image outputs (if any)
        {
            "format": "png",
            "data": "base64...",
            "metadata": {...}
        }
    ],
    # Conditional fields (only present if relevant):
    "error": {                 # Only if execution error occurred
        "type": "syntax_error",
        "message": "SyntaxError: invalid syntax"
    },
    "warning": {              # Only if warning was issued
        "type": "user_warning",
        "message": "UserWarning: deprecated function"
    }
}
```

### Error Types
- `syntax_error` - Python syntax errors
- `name_error` - Undefined variable/function
- `type_error` - Type-related errors
- `value_error` - Invalid value errors
- `zero_division_error` - Division by zero
- `index_error` - List/array index out of bounds
- `key_error` - Dictionary key not found
- `import_error` - Module import failures
- `runtime_error` - Generic runtime errors

### Warning Types
- `user_warning` - General warnings
- `deprecation_warning` - Deprecated functionality
- `future_warning` - Future behavior changes
- `runtime_warning` - Runtime warnings

---

## 📖 API Reference

### Diagnostic Tools

#### `debug_connection_status()`
Get detailed connection and configuration status.

**Parameters:** None

**Returns:**
```python
{
    "config": {
        "ROOM_URL": "http://localhost:8888",
        "ROOM_ID": "notebook.ipynb",
        "ROOM_TOKEN": "MY_TOKEN...",
        "PROVIDER": "jupyter",
        "RUNTIME_URL": "http://localhost:8888"
    },
    "connection_status": {
        "kernel_status": "alive",
        "notebook_connection_exists": True,
        "doc_available": True,
        "cell_count": 42
    }
}
```

**Usage:**
```python
status = await client.call_tool("debug_connection_status")
```

---

### Cell Reading Tools

#### `get_notebook_info()`
Get basic notebook metadata.

**Parameters:** None

**Returns:**
```python
{
    "room_id": "notebook.ipynb",
    "total_cells": 15,
    "cell_types": {
        "markdown": 8,
        "code": 7
    }
}
```

#### `read_all_cells(full_output=False)`
Read all cells from the notebook.

**Parameters:**
- `full_output` (bool): Return complete outputs without truncation

**Returns:** List of [Cell Objects](#cell-objects)

**Usage:**
```python
# Get all cells with truncated outputs
cells = await client.read_all_cells()

# Get all cells with full outputs
cells = await client.read_all_cells(full_output=True)

# Check for errors in any cell
for cell in cells:
    if client.has_error(cell):
        print(f"Cell {cell['cell_index']}: {client.get_error_info(cell)}")
```

#### `read_cell(cell_index)`
Read a specific cell.

**Parameters:**
- `cell_index` (int): 0-based cell index

**Returns:** [Cell Object](#cell-objects)

**Usage:**
```python
cell = await client.read_cell(0)
print(f"Cell content: {cell['content']}")
```

---

### Cell Manipulation Tools

#### `append_markdown_cell(cell_source)`
Add a markdown cell to the end of the notebook.

**Parameters:**
- `cell_source` (str): Markdown content

**Returns:** Success message (str)

**Usage:**
```python
result = await client.append_markdown_cell("# New Section\n\nThis is **bold** text.")
```

#### `insert_markdown_cell(cell_index, cell_source)`
Insert a markdown cell at a specific position.

**Parameters:**
- `cell_index` (int): Position to insert (0-based)
- `cell_source` (str): Markdown content

**Returns:** Success message (str)

#### `overwrite_cell_source(cell_index, cell_source)`
Replace the content of an existing cell.

**Parameters:**
- `cell_index` (int): Target cell index
- `cell_source` (str): New content (must match cell type)

**Returns:** Success message (str)

**Usage:**
```python
await client.overwrite_cell_source(0, "# Updated Title")
```

#### `delete_cell(cell_index)`
Remove a cell from the notebook.

**Parameters:**
- `cell_index` (int): Cell to delete (0-based)

**Returns:** Success message (str)

---

### Code Execution Tools

#### `append_execute_code_cell(cell_source, full_output=False)`
Add and execute a code cell at the end of the notebook.

**Parameters:**
- `cell_source` (str): Python code to execute
- `full_output` (bool): Return complete outputs without truncation

**Returns:** [Cell Object](#cell-objects) with execution results

**Usage:**
```python
# Simple execution
result = await client.append_execute_code_cell("print('Hello, World!')")

# With error handling
result = await client.append_execute_code_cell("x = 1/0")
if client.has_error(result):
    error = client.get_error_info(result)
    print(f"Error: {error['type']} - {error['message']}")

# With full output for large results
result = await client.append_execute_code_cell(
    "for i in range(1000): print(i)", 
    full_output=True
)
```

#### `insert_execute_code_cell(cell_index, cell_source, full_output=False)`
Insert and execute a code cell at a specific position.

**Parameters:**
- `cell_index` (int): Position to insert
- `cell_source` (str): Python code to execute  
- `full_output` (bool): Return complete outputs without truncation

**Returns:** [Cell Object](#cell-objects) with execution results

#### `execute_cell_with_progress(cell_index, timeout_seconds=300, full_output=False)`
Execute an existing cell with progress monitoring.

**Parameters:**
- `cell_index` (int): Cell to execute
- `timeout_seconds` (int): Maximum execution time
- `full_output` (bool): Return complete outputs without truncation

**Returns:**
```python
{
    "text_outputs": ["Output line 1", "Output line 2"],
    "images": [{"format": "png", "data": "..."}],
    # Conditional error/warning fields
}
```

#### `execute_cell_simple_timeout(cell_index, timeout_seconds=300, full_output=False)`
Execute a cell with simple timeout (for short-running cells).

**Parameters:** Same as `execute_cell_with_progress`
**Returns:** Same format as `execute_cell_with_progress`

#### `execute_cell_streaming(cell_index, timeout_seconds=300, progress_interval=5, full_output=False)`
Execute a cell with real-time progress updates (for long-running cells).

**Parameters:**
- `cell_index` (int): Cell to execute
- `timeout_seconds` (int): Maximum execution time
- `progress_interval` (int): Seconds between progress updates
- `full_output` (bool): Return complete outputs without truncation

**Returns:** List of progress strings with timestamps

**Usage:**
```python
# For long-running computations
progress = await client.call_tool("execute_cell_streaming", {
    "cell_index": 5,
    "timeout_seconds": 600,
    "progress_interval": 10
})
for update in progress:
    print(update)
```

---

### Notebook Management Tools

#### `create_notebook(notebook_path, initial_content=None, switch_to_notebook=True)`
Create a new Jupyter notebook.

**Parameters:**
- `notebook_path` (str): Path for new notebook (must end with .ipynb)
- `initial_content` (str, optional): Initial markdown content
- `switch_to_notebook` (bool): Switch MCP context to new notebook

**Returns:** Success message with creation details

**Usage:**
```python
# Create and switch to new notebook
result = await client.create_notebook(
    "analysis/data_exploration.ipynb",
    "# Data Exploration\n\nInitial analysis notebook.",
    switch_to_notebook=True
)
print(result)  # Contains browser URL
```

#### `switch_notebook(notebook_path, close_other_tabs=True)`
Switch MCP context to a different notebook.

**Parameters:**
- `notebook_path` (str): Target notebook path
- `close_other_tabs` (bool): Generate URL that closes other tabs

**Returns:** Success message with browser management URL

#### `list_notebooks(directory_path="", include_subdirectories=True, max_depth=3)`
List all notebooks in the workspace.

**Parameters:**
- `directory_path` (str): Directory to search (empty for root)
- `include_subdirectories` (bool): Search subdirectories
- `max_depth` (int): Maximum search depth

**Returns:**
```python
{
    "notebooks": [
        {
            "name": "analysis.ipynb",
            "path": "notebooks/analysis.ipynb", 
            "created": "2024-01-01T10:00:00Z",
            "last_modified": "2024-01-01T12:00:00Z",
            "size": 15234,
            "writable": True,
            "url": "http://localhost:8888/lab/tree/...",
            "is_current_mcp_context": False
        }
    ],
    "total_found": 15,
    "current_mcp_context": "notebook.ipynb"
}
```

---

### Workspace Management Tools

#### `list_open_notebooks()`
List currently open notebooks in JupyterLab.

**Returns:**
```python
{
    "open_notebooks": [
        {
            "path": "analysis.ipynb",
            "factory": "Notebook",
            "workspace_key": "application-mimedocuments:analysis.ipynb:Notebook"
        }
    ],
    "total_open": 3,
    "current_mcp_context": "notebook.ipynb"
}
```

#### `prepare_notebook(notebook_path)`
One-stop notebook preparation with comprehensive setup.

**Features:**
- ✅ Checks if notebook exists
- ✅ Switches MCP context
- ✅ Creates focused workspace (closes other tabs)
- ✅ Provides browser URL
- ✅ Establishes collaboration session

**Parameters:**
- `notebook_path` (str): Target notebook path

**Returns:** Detailed preparation status with browser URL

**Usage:**
```python
# Complete notebook setup in one call
result = await client.prepare_notebook("analysis/my_research.ipynb")
print(result)  # Contains focused workspace URL
```

---

## 🚨 Error & Warning Detection

The MCP server provides robust error and warning detection with structured information.

### Client Utility Methods

```python
# Check for execution issues
has_error = client.has_error(cell_result)
has_warning = client.has_warning(cell_result)
has_any_issues = client.has_execution_issues(cell_result)

# Get detailed information
error_info = client.get_error_info(cell_result)  # Returns dict or None
warning_info = client.get_warning_info(cell_result)  # Returns dict or None

# Get execution summary
summary = client.get_execution_summary(cell_result)
```

### Error Information Structure
```python
{
    "type": "zero_division_error",
    "message": "ZeroDivisionError: division by zero"
}
```

### Warning Information Structure  
```python
{
    "type": "user_warning", 
    "message": "UserWarning: This function is deprecated"
}
```

### Execution Summary
```python
{
    "has_error": False,
    "has_warning": True,
    "has_output": True,
    "has_images": False,
    "cell_index": 5,
    "warning": {
        "type": "deprecation_warning",
        "message": "DeprecationWarning: Function will be removed"
    }
}
```

---

## 📝 Response Formats

### Standard Cell Object
```python
{
    "cell_index": 0,
    "cell_id": "unique-id",
    "content": "source code or markdown",
    "output": ["output line 1", "output line 2"],
    "images": [
        {
            "format": "png",
            "data": "base64-encoded-data",
            "metadata": {"width": 400, "height": 300}
        }
    ],
    # Conditional fields (only present when relevant):
    "error": {"type": "error_type", "message": "error details"},
    "warning": {"type": "warning_type", "message": "warning details"}
}
```

### Success Messages
Most manipulation operations return descriptive success messages:
```
"Jupyter Markdown cell added and confirmed at position 5."
"Cell 3 (code) deleted successfully and confirmed."
```

### Error Responses
API errors are raised as exceptions with descriptive messages:
```python
try:
    result = await client.read_cell(999)
except Exception as e:
    print(f"API Error: {e}")
```

---

## 🎯 Usage Patterns

### 1. Basic Notebook Interaction
```python
# Connect and explore
client = MCPClient("http://localhost:4040")
info = await client.get_notebook_info()
cells = await client.read_all_cells()

# Add content
await client.append_markdown_cell("# Analysis Results")
result = await client.append_execute_code_cell("import pandas as pd")
```

### 2. Error-Aware Code Execution
```python
def execute_with_error_handling(code):
    result = await client.append_execute_code_cell(code)
    
    if client.has_error(result):
        error = client.get_error_info(result)
        print(f"❌ {error['type']}: {error['message']}")
        return None
    elif client.has_warning(result):
        warning = client.get_warning_info(result)
        print(f"⚠️  {warning['type']}: {warning['message']}")
    
    return result
```

### 3. Batch Operations with Progress
```python
# Execute multiple cells with progress tracking
code_cells = [
    "import numpy as np",
    "data = np.random.randn(1000, 1000)",
    "result = np.linalg.eig(data)",
    "print(f'Eigenvalues computed: {len(result[0])}')"
]

for i, code in enumerate(code_cells):
    print(f"Executing step {i+1}/{len(code_cells)}")
    result = await client.append_execute_code_cell(code)
    
    if client.has_execution_issues(result):
        summary = client.get_execution_summary(result)
        print(f"Issues in step {i+1}: {summary}")
        break
```

### 4. Notebook Management Workflow
```python
# Create project structure
await client.create_notebook("analysis/01_data_loading.ipynb", 
                           "# Data Loading\n\nLoad and preprocess data")
await client.create_notebook("analysis/02_exploration.ipynb",
                           "# Data Exploration\n\nExplore data patterns")

# List all project notebooks
notebooks = await client.list_notebooks("analysis/")
print(f"Created {notebooks['total_found']} notebooks")

# Switch between notebooks as needed
await client.switch_notebook("analysis/01_data_loading.ipynb")
```

### 5. Long-Running Computations
```python
# For computations that take minutes
await client.append_execute_code_cell("""
import time
import numpy as np

print("Starting large computation...")
large_matrix = np.random.randn(5000, 5000)
for i in range(10):
    result = np.linalg.svd(large_matrix)
    print(f"Iteration {i+1}/10 completed")
    time.sleep(2)
print("Computation finished!")
""")

# Execute with streaming progress
cells = await client.read_all_cells()
last_cell_index = len(cells) - 1

progress = await client.call_tool("execute_cell_streaming", {
    "cell_index": last_cell_index,
    "timeout_seconds": 600,
    "progress_interval": 10
})

for update in progress:
    print(f"Progress: {update}")
```

---

## 💡 Examples

### Agent-Powered Data Analysis
```python
class DataAnalysisAgent:
    def __init__(self, mcp_url="http://localhost:4040"):
        self.client = MCPClient(mcp_url)
    
    async def setup_analysis_notebook(self, dataset_path):
        # Create dedicated analysis notebook
        notebook_path = f"analysis_{dataset_path.replace('/', '_')}.ipynb"
        await self.client.create_notebook(
            notebook_path,
            f"# Automated Analysis: {dataset_path}\n\nGenerated by AI agent"
        )
        
        # Setup imports and load data
        setup_code = f"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Load dataset
data = pd.read_csv('{dataset_path}')
print(f"Loaded dataset: {{data.shape}}")
data.head()
"""
        result = await self.client.append_execute_code_cell(setup_code)
        
        if self.client.has_error(result):
            error = self.client.get_error_info(result)
            raise Exception(f"Data loading failed: {error['message']}")
        
        return result
    
    async def generate_summary_stats(self):
        stats_code = """
# Generate summary statistics
print("Dataset Summary:")
print("=" * 50)
print(f"Shape: {data.shape}")
print(f"Memory usage: {data.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
print()
print("Data types:")
print(data.dtypes)
print()
print("Missing values:")
print(data.isnull().sum())
print()
print("Summary statistics:")
data.describe()
"""
        return await self.client.append_execute_code_cell(stats_code)
    
    async def run_full_analysis(self, dataset_path):
        try:
            # Setup
            await self.setup_analysis_notebook(dataset_path)
            
            # Generate insights
            await self.generate_summary_stats()
            
            # Add visualizations
            viz_code = """
# Create visualizations
fig, axes = plt.subplots(2, 2, figsize=(15, 10))

# Distribution plots for numeric columns
numeric_cols = data.select_dtypes(include=[np.number]).columns[:4]
for i, col in enumerate(numeric_cols):
    if i < 4:
        row, col_idx = i // 2, i % 2
        axes[row, col_idx].hist(data[col], bins=30, alpha=0.7)
        axes[row, col_idx].set_title(f'Distribution of {col}')

plt.tight_layout()
plt.show()
"""
            viz_result = await self.client.append_execute_code_cell(viz_code)
            
            # Check for any issues
            summary = self.client.get_execution_summary(viz_result)
            if summary['has_error']:
                print(f"Visualization error: {summary['error']['message']}")
            
            return True
            
        except Exception as e:
            print(f"Analysis failed: {e}")
            return False

# Usage
agent = DataAnalysisAgent()
success = await agent.run_full_analysis("datasets/sales_data.csv")
```

### Interactive Debugging Assistant
```python
class DebuggingAssistant:
    def __init__(self, mcp_url="http://localhost:4040"):
        self.client = MCPClient(mcp_url)
        self.error_fixes = {
            "name_error": "Check variable names and ensure they're defined",
            "syntax_error": "Review syntax for missing brackets, quotes, or colons",
            "type_error": "Verify data types and operations compatibility",
            "zero_division_error": "Add zero-division checks before division operations"
        }
    
    async def analyze_notebook_errors(self):
        cells = await self.client.read_all_cells()
        error_cells = []
        
        for cell in cells:
            if self.client.has_error(cell):
                error_info = self.client.get_error_info(cell)
                error_cells.append({
                    "cell_index": cell["cell_index"],
                    "content": cell["content"][:100] + "...",
                    "error": error_info
                })
        
        return error_cells
    
    async def suggest_fixes(self):
        error_cells = await self.analyze_notebook_errors()
        
        if not error_cells:
            await self.client.append_markdown_cell("✅ No errors found in notebook!")
            return
        
        # Create error report
        report = "# 🔧 Error Analysis Report\n\n"
        for i, error_cell in enumerate(error_cells, 1):
            error_type = error_cell["error"]["type"]
            suggestion = self.error_fixes.get(error_type, "Review the error message for clues")
            
            report += f"## Error {i}: Cell {error_cell['cell_index']}\n\n"
            report += f"**Type:** `{error_type}`\n\n" 
            report += f"**Message:** {error_cell['error']['message']}\n\n"
            report += f"**Code Preview:** `{error_cell['content']}`\n\n"
            report += f"**Suggestion:** {suggestion}\n\n"
            report += "---\n\n"
        
        await self.client.append_markdown_cell(report)

# Usage
debugger = DebuggingAssistant()
await debugger.suggest_fixes()
```

---

## 🔧 Advanced Configuration

### Custom Timeouts
```python
# For long-running computations
result = await client.call_tool("execute_cell_with_progress", {
    "cell_index": 0,
    "timeout_seconds": 1800,  # 30 minutes
    "full_output": True
})
```

### Parallel Execution Monitoring
```python
import asyncio

async def monitor_multiple_cells():
    tasks = []
    for i in range(5):
        task = client.call_tool("execute_cell_simple_timeout", {
            "cell_index": i,
            "timeout_seconds": 60
        })
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Cell {i} failed: {result}")
        elif client.has_execution_issues(result):
            summary = client.get_execution_summary(result)
            print(f"Cell {i} issues: {summary}")
```

### Error Recovery Patterns
```python
async def robust_execution(code, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = await client.append_execute_code_cell(code)
            
            if not client.has_error(result):
                return result
            
            error = client.get_error_info(result)
            print(f"Attempt {attempt + 1} failed: {error['type']}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
        except Exception as e:
            print(f"API error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    
    raise Exception(f"Failed after {max_retries} attempts")
```

---

This comprehensive API documentation provides everything you need to build sophisticated agent platforms that interact with Jupyter notebooks through the MCP protocol. The structured error/warning detection system enables robust execution monitoring, while the rich set of tools supports everything from simple automation to complex multi-notebook workflows. 