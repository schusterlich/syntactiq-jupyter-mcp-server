# 🪐✨ Syntactiq Jupyter MCP Server

**Real-time Jupyter Notebook control through the Model Context Protocol**

A comprehensive [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server implementation that provides **robust, real-time** interaction with 📓 Jupyter Notebooks. Perfect for building AI agents, automation platforms, and interactive data analysis workflows.

> **Note**: This project is based on the original [Datalayer Jupyter MCP Server](https://github.com/datalayer/jupyter-mcp-server) but has been extensively enhanced with new features, comprehensive error handling, and production-ready capabilities.

## ✨ Key Features

- 🚀 **Real-time Control**: Instant notebook manipulation with live synchronization
- 🔍 **Intelligent Error Detection**: Structured error and warning detection for Python code
- 🖼️ **Rich Output Support**: Handles text, images, and complex visualizations
- 📊 **Progress Monitoring**: Real-time execution tracking for long-running operations
- 🎯 **Smart Output Management**: Automatic truncation with full-output options
- 🔄 **Notebook Management**: Create, switch, and organize notebooks seamlessly
- 🧪 **Comprehensive Testing**: 59 automated tests ensuring reliability
- 🤖 **Agent-Ready**: Perfect foundation for building AI-powered notebook agents

## 🏗️ Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Platform / Client                      │
│  ┌─────────────────┐                    ┌─────────────────────┐ │
│  │   AI Agent      │                    │   Web Interface     │ │
│  │   (Python)      │◄──────────────────►│   (Browser/App)     │ │
│  └─────────────────┘                    └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                          │                            │
                     HTTP/MCP                      HTTP/WebSocket
                          ▼                            ▼
   ┌─────────────────────────────────────────────────────────────┐
   │              Docker Compose Services                        │
   │  ┌─────────────────┐          ┌─────────────────────────┐   │
   │  │  MCP Server     │          │    JupyterLab           │   │
   │  │  :4040          │◄────────►│    :8888                │   │
   │  │  • 19 MCP Tools │ WebSocket│    • Real-time Collab   │   │
   │  │  • Error Detect │  RTC API │    • Multi-notebook     │   │
   │  │  • Progress Mon │          │    • Rich Outputs       │   │
   │  └─────────────────┘          └─────────────────────────┘   │
   └─────────────────────────────────────────────────────────────┘
```

### Integration Layer

- **MCP Protocol**: JSON-RPC 2.0 over HTTP with Server-Sent Events
- **Real-time Sync**: WebSocket-based collaboration with Jupyter's RTC API
- **Error Detection**: Regex-based Python error/warning parsing with structured output
- **Output Processing**: Smart truncation, image extraction, and progress monitoring

## 🚀 Quick Start

### 1. Launch Services

```bash
# Clone and start
git clone <repository>
cd syntactiq-jupyter-mcp
./quick_start.sh
```

This starts:
- **JupyterLab**: http://localhost:8888 (token: `MY_TOKEN`)
- **MCP Server**: http://localhost:4040

### 2. Test Basic Functionality

```bash
# Quick connection test
python -c "
import asyncio
from mcp_client import MCPClient

async def test():
    client = MCPClient('http://localhost:4040')
    info = await client.get_notebook_info()
    print(f'✅ Connected to: {info[\"room_id\"]}')
    
    # Test error detection
    result = await client.append_execute_code_cell('print(\"Hello MCP!\")')
    print(f'✅ Execution successful: {result[\"output\"]}')

asyncio.run(test())
"
```

### 3. Open JupyterLab

Open http://localhost:8888?token=MY_TOKEN in your browser to see real-time changes as your agent interacts with notebooks.

## 🧪 Running Tests

### Comprehensive Test Suite

```bash
# Run full MCP integration tests (59 tests)
python tests/mcp_test_suite.py
```

This comprehensive suite tests:
- ✅ All 19 MCP tools functionality
- ✅ Error and warning detection system  
- ✅ Notebook management operations
- ✅ Cell manipulation and execution
- ✅ Output handling and truncation
- ✅ Connection resilience and recovery
- ✅ Edge cases and error conditions

### Unit Tests

```bash
# Run focused unit tests for detection logic
python tests/unit_test_suite.py
```

Tests the core detection algorithms:
- ✅ Error pattern recognition (9 error types)
- ✅ Warning pattern detection (4 warning types)
- ✅ False positive prevention
- ✅ Edge case handling

## 📖 MCP Tools Reference

### 🔍 Diagnostic Tools

#### `debug_connection_status()`
Get detailed connection and configuration status.

**Parameters**: None  
**Returns**: 
```python
{
    "config": {"ROOM_URL": "...", "ROOM_ID": "notebook.ipynb"},
    "connection_status": {"kernel_status": "alive", "cell_count": 42}
}
```

---

### 📚 Reading Tools

#### `get_notebook_info()`
Get basic notebook metadata.

**Parameters**: None  
**Returns**: 
```python
{
    "room_id": "notebook.ipynb",
    "total_cells": 15,
    "cell_types": {"markdown": 8, "code": 7}
}
```

#### `read_all_cells(full_output=False)`
Read all cells from the notebook.

**Parameters**: 
- `full_output` (bool): Return complete outputs without truncation

**Returns**: Array of cell objects
```python
[{
    "cell_index": 0,
    "cell_id": "unique-id",
    "content": "print('hello')",
    "output": ["hello"],
    "images": [],
    # Conditional error/warning fields
}]
```

#### `read_cell(cell_index)`
Read a specific cell.

**Parameters**: 
- `cell_index` (int): 0-based cell position

**Returns**: Single cell object (same format as above)

---

### ✏️ Cell Manipulation Tools

#### `append_markdown_cell(cell_source)`
Add markdown cell to the end of the notebook.

**Parameters**: 
- `cell_source` (str): Markdown content

**Returns**: `"Jupyter Markdown cell added and confirmed at position 5."`

#### `insert_markdown_cell(cell_index, cell_source)`
Insert markdown cell at specific position.

**Parameters**: 
- `cell_index` (int): Position to insert
- `cell_source` (str): Markdown content

**Returns**: `"Jupyter Markdown cell inserted and confirmed at position 2."`

#### `overwrite_cell_source(cell_index, cell_source)`
Replace content of existing cell.

**Parameters**: 
- `cell_index` (int): Target cell
- `cell_source` (str): New content

**Returns**: `"Cell 3 overwritten successfully and confirmed - use execute_cell to execute it if code"`

#### `delete_cell(cell_index)`
Remove cell from notebook.

**Parameters**: 
- `cell_index` (int): Cell to delete

**Returns**: `"Cell 3 (code) deleted successfully and confirmed."`

---

### ⚡ Code Execution Tools

#### `append_execute_code_cell(cell_source, full_output=False)`
Add and execute code cell.

**Parameters**: 
- `cell_source` (str): Python code
- `full_output` (bool): Return complete outputs

**Returns**: 
```python
{
    "cell_index": 5,
    "cell_id": "abc123",
    "content": "x = 1/0",
    "output": [],
    "images": [],
    "error": {  # Only if error occurred
        "type": "zero_division_error",
        "message": "ZeroDivisionError: division by zero"
    }
}
```

#### `insert_execute_code_cell(cell_index, cell_source, full_output=False)`
Insert and execute code cell at position.

**Parameters**: 
- `cell_index` (int): Position to insert
- `cell_source` (str): Python code
- `full_output` (bool): Return complete outputs

**Returns**: Same format as `append_execute_code_cell`

#### `execute_cell_with_progress(cell_index, timeout_seconds=300, full_output=False)`
Execute existing cell with progress monitoring.

**Parameters**: 
- `cell_index` (int): Cell to execute
- `timeout_seconds` (int): Max execution time
- `full_output` (bool): Return complete outputs

**Returns**: 
```python
{
    "text_outputs": ["Result line 1", "Result line 2"],
    "images": [{"format": "png", "data": "base64..."}],
    # Optional error/warning fields
}
```

#### `execute_cell_simple_timeout(cell_index, timeout_seconds=300, full_output=False)`
Execute cell with simple timeout (for short operations).

**Parameters**: Same as `execute_cell_with_progress`  
**Returns**: Same format as `execute_cell_with_progress`

#### `execute_cell_streaming(cell_index, timeout_seconds=300, progress_interval=5, full_output=False)`
Execute cell with real-time progress updates.

**Parameters**: 
- `cell_index` (int): Cell to execute
- `timeout_seconds` (int): Max execution time  
- `progress_interval` (int): Seconds between updates
- `full_output` (bool): Return complete outputs

**Returns**: Array of progress strings with timestamps
```python
["[5.2s] Starting computation...", "[15.8s] Progress: 50%", "[COMPLETED in 28.3s]"]
```

---

### 📁 Notebook Management Tools

#### `create_notebook(notebook_path, initial_content=None, switch_to_notebook=True)`
Create new Jupyter notebook.

**Parameters**: 
- `notebook_path` (str): Path ending with .ipynb
- `initial_content` (str): Optional initial markdown
- `switch_to_notebook` (bool): Switch MCP context

**Returns**: `"Notebook created at: analysis.ipynb. MCP context switched. Open: http://localhost:8888/lab/tree/analysis.ipynb?token=MY_TOKEN"`

#### `switch_notebook(notebook_path, close_other_tabs=True)`
Switch MCP context to different notebook.

**Parameters**: 
- `notebook_path` (str): Target notebook
- `close_other_tabs` (bool): Generate focused URL

**Returns**: Detailed message with browser management URL

#### `list_notebooks(directory_path="", include_subdirectories=True, max_depth=3)`
List all notebooks in workspace.

**Parameters**: 
- `directory_path` (str): Directory to search
- `include_subdirectories` (bool): Search subdirs
- `max_depth` (int): Max search depth

**Returns**: 
```python
{
    "notebooks": [{"name": "analysis.ipynb", "path": "notebooks/analysis.ipynb", "size": 15234, "is_current_mcp_context": True}],
    "total_found": 15,
    "current_mcp_context": "notebook.ipynb"
}
```

#### `list_open_notebooks()`
List currently open notebooks in JupyterLab.

**Parameters**: None  
**Returns**: 
```python
{
    "open_notebooks": [{"path": "analysis.ipynb", "factory": "Notebook"}],
    "total_open": 3,
    "current_mcp_context": "notebook.ipynb"
}
```

#### `prepare_notebook(notebook_path)`
One-stop notebook preparation with comprehensive setup.

**Parameters**: 
- `notebook_path` (str): Target notebook

**Returns**: Complete preparation status with focused workspace URL

---

## 🤖 Special LLM Features

### 🚨 Error & Warning Detection

**Automatic Detection**: All execution tools detect and structure Python errors/warnings.

**Error Types Detected**:
- `syntax_error`, `name_error`, `type_error`, `value_error`
- `zero_division_error`, `index_error`, `key_error`
- `import_error`, `runtime_error`

**Warning Types Detected**:
- `user_warning`, `deprecation_warning`, `future_warning`, `runtime_warning`

**Usage**:
```python
result = await client.append_execute_code_cell("x = 1/0")
if client.has_error(result):
    error = client.get_error_info(result)
    print(f"Error: {error['type']} - {error['message']}")
```

### 📊 Smart Output Management

**Automatic Truncation**: Long outputs are truncated by default for LLM context efficiency.

```python
# Default: truncated for LLM efficiency
result = await client.append_execute_code_cell("print('x' * 2000)")
# result['output'] = ["xxx...[TRUNCATED - 1500+ chars]...Use full_output=True for complete result"]

# Full output when needed
result = await client.append_execute_code_cell("print('x' * 2000)", full_output=True)
# result['output'] = ["xxxxxxx..."] # Complete 2000 character output
```

### 🖼️ Rich Image Support

**Automatic Image Detection**: Extracts and structures image outputs from matplotlib, plotly, etc.

```python
result = await client.append_execute_code_cell("""
import matplotlib.pyplot as plt
plt.plot([1,2,3], [1,4,9])
plt.show()
""")

print(result['images'])
# [{"format": "png", "data": "iVBORw0KGgoAAAANSUhEUgAA...", "metadata": {"width": 640, "height": 480}}]
```

### ⏱️ Progress Monitoring

**Real-time Tracking**: Monitor long-running operations with live updates.

```python
# For long computations
progress = await client.call_tool("execute_cell_streaming", {
    "cell_index": 5,
    "timeout_seconds": 600,
    "progress_interval": 10
})

for update in progress:
    print(update)
# [15.2s] Starting large computation...
# [25.8s] Progress: 30% completed
# [COMPLETED in 180.5s]
```

## 🎯 Agent Development

### Quick Agent Example

```python
from mcp_client import MCPClient

class DataAnalysisAgent:
    def __init__(self):
        self.client = MCPClient("http://localhost:4040")
    
    async def analyze_dataset(self, csv_path):
        # Create analysis notebook
        await self.client.create_notebook("analysis.ipynb", "# Data Analysis")
        
        # Load and analyze data
        result = await self.client.append_execute_code_cell(f"""
import pandas as pd
df = pd.read_csv('{csv_path}')
print(f"Dataset shape: {{df.shape}}")
df.describe()
""")
        
        # Check for issues
        if self.client.has_error(result):
            error = self.client.get_error_info(result)
            return f"Analysis failed: {error['message']}"
        
        return f"Analysis complete! Dataset has {len(result['output'])} outputs"

# Usage
agent = DataAnalysisAgent()
result = await agent.analyze_dataset("data.csv")
```

See `agent_examples.py` for comprehensive agent development patterns.

## 📚 Documentation

- **[Complete API Documentation](MCP_API_DOCUMENTATION.md)** - Detailed reference with examples
- **[Quick Reference Guide](MCP_API_QUICK_REFERENCE.md)** - Essential tools and patterns
- **[Agent Examples](agent_examples.py)** - Practical agent development examples

## 🔧 Development

### Environment Setup

```bash
# Start development environment
./quick_start.sh

# Run comprehensive tests
python tests/mcp_test_suite.py

# Run unit tests
python tests/unit_test_suite.py

# Test with Python client
python -c "
import asyncio
from mcp_client import MCPClient

async def demo():
    client = MCPClient('http://localhost:4040')
    # Your agent code here
    
asyncio.run(demo())
"
```

### Production Deployment

The architecture supports scaling from development to production:

- **Development**: Single container with shared services
- **Single-User**: One container per user
- **Multi-User**: Full orchestration with container management

See architecture diagrams above for detailed deployment patterns.

## 🏆 Credits & License

This project builds upon the excellent foundation provided by [Datalayer's Jupyter MCP Server](https://github.com/datalayer/jupyter-mcp-server). While extensively enhanced with new features and capabilities, we acknowledge and appreciate the original work.

**Key Enhancements Added**:
- Comprehensive error and warning detection system
- 59-test automated test suite with 100% success rate
- Smart output truncation and image handling
- Progress monitoring for long-running operations
- Extensive notebook management capabilities
- Agent development framework and examples
- Production-ready architecture patterns

**Original Credits**: [Datalayer Team](https://datalayer.io) for the foundational MCP server implementation.

**License**: BSD 3-Clause License (same as original)

---

*Build powerful AI agents that interact seamlessly with Jupyter notebooks through the standardized Model Context Protocol.* 🚀
