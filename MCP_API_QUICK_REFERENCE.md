# MCP API Quick Reference

**Base URL**: `http://localhost:4040` | **Endpoint**: `/mcp`

## 🏗️ Setup
```python
from mcp_client import MCPClient
client = MCPClient("http://localhost:4040")
```

## 📖 Essential Tools

### Information & Reading
```python
# Get notebook info
info = await client.get_notebook_info()

# Read all cells
cells = await client.read_all_cells(full_output=False)

# Read specific cell  
cell = await client.read_cell(cell_index=0)
```

### Cell Creation & Manipulation
```python
# Add markdown cell
await client.append_markdown_cell("# New Section")

# Insert markdown at position
await client.insert_markdown_cell(1, "# Inserted Section")

# Overwrite cell content
await client.overwrite_cell_source(0, "# Updated Content")

# Delete cell
await client.delete_cell(2)
```

### Code Execution
```python
# Execute code (returns cell object with error/warning detection)
result = await client.append_execute_code_cell("print('Hello')")

# Execute at specific position
result = await client.insert_execute_code_cell(0, "import pandas as pd")

# Execute existing cell with progress
result = await client.call_tool("execute_cell_with_progress", {
    "cell_index": 5,
    "timeout_seconds": 300,
    "full_output": False
})
```

### Notebook Management
```python
# Create new notebook
await client.create_notebook("analysis.ipynb", "# Analysis", switch_to_notebook=True)

# Switch notebook context
await client.switch_notebook("other.ipynb", close_other_tabs=True)

# List notebooks
notebooks = await client.list_notebooks()

# One-stop notebook preparation
await client.prepare_notebook("target.ipynb")
```

## 🚨 Error & Warning Detection

### Check for Issues
```python
# Check for errors/warnings
has_error = client.has_error(result)
has_warning = client.has_warning(result)  
has_issues = client.has_execution_issues(result)

# Get detailed info
error_info = client.get_error_info(result)      # {type, message} or None
warning_info = client.get_warning_info(result)  # {type, message} or None

# Full execution summary
summary = client.get_execution_summary(result)
```

### Error Types
- `syntax_error`, `name_error`, `type_error`, `value_error`
- `zero_division_error`, `index_error`, `key_error`
- `import_error`, `runtime_error`

### Warning Types  
- `user_warning`, `deprecation_warning`, `future_warning`, `runtime_warning`

## 📦 Cell Object Format
```python
{
    "cell_index": 0,
    "cell_id": "unique-id", 
    "content": "source code",
    "output": ["output lines"],
    "images": [{"format": "png", "data": "base64..."}],
    # Conditional fields (only when relevant):
    "error": {"type": "error_type", "message": "details"},
    "warning": {"type": "warning_type", "message": "details"}
}
```

## 🎯 Common Patterns

### Error-Aware Execution
```python
result = await client.append_execute_code_cell(code)
if client.has_error(result):
    error = client.get_error_info(result)
    print(f"❌ {error['type']}: {error['message']}")
else:
    print(f"✅ Output: {result['output']}")
```

### Batch Processing
```python
codes = ["import numpy as np", "data = np.random.randn(100)", "print(data.mean())"]
for i, code in enumerate(codes):
    result = await client.append_execute_code_cell(code)
    if client.has_execution_issues(result):
        print(f"Issue in step {i+1}: {client.get_execution_summary(result)}")
        break
```

### Robust Notebook Creation
```python
# Create and setup analysis notebook
await client.create_notebook("analysis/results.ipynb", "# Results Analysis")
await client.append_markdown_cell("## Data Loading")
result = await client.append_execute_code_cell("import pandas as pd")

if client.has_error(result):
    print("Setup failed:", client.get_error_info(result))
else:
    print("Notebook ready for analysis!")
```

## 🔧 All Available Tools

**Diagnostic**: `debug_connection_status`

**Reading**: `get_notebook_info`, `read_all_cells`, `read_cell`

**Manipulation**: `append_markdown_cell`, `insert_markdown_cell`, `overwrite_cell_source`, `delete_cell`

**Execution**: `append_execute_code_cell`, `insert_execute_code_cell`, `execute_cell_with_progress`, `execute_cell_simple_timeout`, `execute_cell_streaming`

**Notebooks**: `create_notebook`, `switch_notebook`, `list_notebooks`, `list_open_notebooks`, `prepare_notebook`

---

💡 **Full Documentation**: See `MCP_API_DOCUMENTATION.md` for complete details, examples, and advanced usage patterns. 