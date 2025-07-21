# Jupyter MCP Server - Implementation Analysis & Tools Documentation

## Overview

The **Jupyter MCP Server** is a comprehensive [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server implementation that enables real-time interaction with Jupyter Notebooks. It allows AI agents to edit, document, and execute code in Jupyter environments for data analysis, visualization, and computational tasks.

**Version:** 0.10.2  
**Provider:** Datalayer, Inc.  
**License:** BSD 3-Clause  

## Architecture

### Core Components

#### 1. **FastMCP Server with CORS (`FastMCPWithCORS`)**
- Extends the standard `FastMCP` class to add CORS middleware support
- Supports both `streamable-http` and `sse` (Server-Sent Events) transports
- Enables cross-origin requests for web-based integrations
- Configured for production use with customizable CORS policies

#### 2. **Kernel Management**
- **Kernel Client**: Uses `jupyter-kernel-client` for Python kernel communication
- **Auto-Recovery**: Automatic kernel restart on failure or disconnection
- **Health Monitoring**: Built-in kernel alive checks and status monitoring
- **Execution Safety**: Timeout handling and interrupt capabilities

#### 3. **Notebook Communication**
- **Real-time Sync**: Uses `jupyter-nbmodel-client` for live notebook collaboration
- **WebSocket Connection**: Real-time bidirectional communication with Jupyter server
- **Document Synchronization**: Built on Y.js CRDT (Conflict-free Replicated Data Types)
- **Connection Recovery**: Automatic reconnection on websocket failures

#### 4. **Transport Layer**
- **stdio**: Standard input/output for direct client integration
- **streamable-http**: HTTP-based transport for web services (port 4040 default)
- **CORS Support**: Cross-origin resource sharing for browser compatibility

### Data Models

#### `RoomRuntime` (Pydantic Model)
```python
class RoomRuntime(BaseModel):
    provider: str           # "jupyter" or "datalayer"
    room_url: str          # Jupyter server URL
    room_id: str           # Notebook path/identifier
    room_token: str        # Authentication token for room
    runtime_url: str       # Kernel runtime URL
    runtime_id: str        # Kernel identifier
    runtime_token: str     # Authentication token for runtime
```

### Utility Functions

#### Output Processing (`utils.py`)
- **`extract_output()`**: Handles multiple Jupyter output formats (traditional dict, CRDT objects, pycrdt._text.Text)
- **`strip_ansi_codes()`**: Removes terminal escape sequences from output
- **`safe_extract_outputs()`**: Safely processes cell outputs with error handling

#### Error Handling
- **Connection Recovery**: Automatic retry logic for websocket disconnections
- **Timeout Management**: Configurable execution timeouts with progress monitoring
- **Graceful Degradation**: Partial output recovery on failures

## MCP Tools

The server provides 12 primary tools for notebook interaction:

### 1. **Notebook Information Tools**

#### `get_notebook_info()`
- **Purpose**: Get basic notebook metadata
- **Returns**: Dictionary with room_id, total_cells, and cell_types count
- **Use Case**: Initial exploration and understanding notebook structure

#### `read_all_cells()`
- **Purpose**: Read all cells in the notebook
- **Returns**: List of cell dictionaries with index, type, source, and outputs
- **Use Case**: Full notebook analysis and content review

#### `read_cell(cell_index: int)`
- **Purpose**: Read a specific cell by index
- **Parameters**: `cell_index` (0-based)
- **Returns**: Cell dictionary with metadata and content
- **Use Case**: Targeted cell inspection

### 2. **Cell Creation Tools**

#### `append_markdown_cell(cell_source: str)`
- **Purpose**: Add markdown cell at the end of notebook
- **Parameters**: `cell_source` (markdown content)
- **Returns**: Success message
- **Use Case**: Documentation and narrative text

#### `insert_markdown_cell(cell_index: int, cell_source: str)`
- **Purpose**: Insert markdown cell at specific position
- **Parameters**: `cell_index` (0-based), `cell_source`
- **Returns**: Success message
- **Use Case**: Contextual documentation insertion

#### `append_execute_code_cell(cell_source: str)`
- **Purpose**: Add and execute code cell at notebook end
- **Parameters**: `cell_source` (Python code)
- **Returns**: List of execution outputs
- **Use Case**: Quick code execution and analysis

#### `insert_execute_code_cell(cell_index: int, cell_source: str)`
- **Purpose**: Insert and execute code cell at specific position
- **Parameters**: `cell_index`, `cell_source`
- **Returns**: List of execution outputs
- **Use Case**: Contextual code insertion and execution

### 3. **Cell Modification Tools**

#### `overwrite_cell_source(cell_index: int, cell_source: str)`
- **Purpose**: Modify existing cell content without execution
- **Parameters**: `cell_index`, `cell_source`
- **Returns**: Success message
- **Note**: Preserves cell type, requires separate execution for code cells
- **Use Case**: Code editing and refinement

#### `delete_cell(cell_index: int)`
- **Purpose**: Remove cell from notebook
- **Parameters**: `cell_index`
- **Returns**: Success message with deleted cell info
- **Use Case**: Cleanup and notebook organization

### 4. **Advanced Execution Tools**

#### `execute_cell_with_progress(cell_index: int, timeout_seconds: int = 300)`
- **Purpose**: Execute cell with real-time progress monitoring
- **Parameters**: `cell_index`, `timeout_seconds` (default: 300)
- **Features**:
  - Real-time output streaming
  - Forced synchronization attempts
  - Progress logging
  - Timeout handling with partial output recovery
- **Returns**: List of outputs with progress information
- **Use Case**: Long-running computations with monitoring

#### `execute_cell_simple_timeout(cell_index: int, timeout_seconds: int = 300)`
- **Purpose**: Simple cell execution with timeout (no real-time sync)
- **Parameters**: `cell_index`, `timeout_seconds`
- **Features**: Reliable execution for short-running cells
- **Returns**: List of execution outputs
- **Use Case**: Quick, reliable code execution

#### `execute_cell_streaming(cell_index: int, timeout_seconds: int = 300, progress_interval: int = 5)`
- **Purpose**: Execute with streaming progress updates
- **Parameters**: `cell_index`, `timeout_seconds`, `progress_interval`
- **Features**:
  - Periodic progress reports
  - Real-time output capture
  - Execution timing information
  - Detailed progress logging
- **Returns**: List of outputs with timestamped progress
- **Use Case**: Long-running analysis with detailed monitoring

## Configuration

### Environment Variables

#### Core Settings
- `TRANSPORT`: "stdio" or "streamable-http"
- `PROVIDER`: "jupyter" or "datalayer"
- `PORT`: HTTP transport port (default: 4040)

#### Runtime Configuration
- `RUNTIME_URL`: Jupyter server URL (default: "http://localhost:8888")
- `START_NEW_RUNTIME`: Boolean to start new kernel (default: true)
- `RUNTIME_ID`: Specific kernel ID (optional)
- `RUNTIME_TOKEN`: Authentication token for runtime

#### Room Configuration
- `ROOM_URL`: Jupyter server URL for notebook access
- `ROOM_ID`: Notebook path/identifier (default: "notebook.ipynb")
- `ROOM_TOKEN`: Authentication token for notebook access

### API Endpoints

#### `/api/connect` [PUT]
- **Purpose**: Dynamic connection to room and runtime
- **Body**: `RoomRuntime` JSON object
- **Response**: Success/error status
- **Use Case**: Runtime reconfiguration

#### `/api/stop` [DELETE]
- **Purpose**: Stop current kernel
- **Response**: Success/error status
- **Use Case**: Resource cleanup

#### `/api/healthz` [GET]
- **Purpose**: Health check with kernel status
- **Response**: Service and kernel status information
- **Use Case**: Monitoring and diagnostics

## Dependencies

### Core Dependencies
- `jupyter-kernel-client>=0.7.3`: Kernel communication
- `jupyter-nbmodel-client>=0.13.5`: Notebook real-time collaboration
- `mcp[cli]>=1.10.1`: Model Context Protocol implementation
- `pydantic`: Data validation and serialization
- `uvicorn`: ASGI server for HTTP transport
- `click`: CLI interface
- `fastapi`: Web framework for HTTP endpoints

### Special Dependencies
- `datalayer_pycrdt==0.12.17`: Specific CRDT implementation for real-time collaboration
- Note: Standard `pycrdt` is explicitly uninstalled in favor of Datalayer's version

### Optional Dependencies
- **test**: `ipykernel`, `jupyter_server>=1.6,<3`, `pytest>=7.0`
- **lint**: `mdformat>0.7`, `mdformat-gfm>=0.3.5`, `ruff`
- **typing**: `mypy>=0.990`

## Implementation Details

### Execution Strategy
1. **Kernel Lifecycle Management**: Automatic start/stop/restart with health monitoring
2. **Connection Resilience**: Multi-retry logic for websocket connections
3. **Output Processing**: Handles multiple Jupyter output formats and CRDT structures
4. **Real-time Synchronization**: Forces document updates during long executions
5. **Error Recovery**: Graceful handling of timeouts, interrupts, and connection failures

### Performance Considerations
- **Async Operations**: All notebook operations are asynchronous
- **Connection Pooling**: Reuses websocket connections where possible
- **Memory Management**: Proper cleanup of notebook clients and kernels
- **Timeout Handling**: Configurable timeouts prevent hanging operations

### Security Features
- **Token-based Authentication**: Support for Jupyter token authentication
- **CORS Configuration**: Configurable cross-origin policies
- **Input Validation**: Pydantic models for request validation
- **Error Sanitization**: Safe error message handling

## Integration Patterns

### Direct Integration
- Use `stdio` transport for direct client-server communication
- Suitable for desktop applications and command-line tools

### Web Service Integration
- Use `streamable-http` transport for REST API access
- Suitable for web applications and microservices
- Requires CORS configuration for browser clients

### Container Deployment
- Docker image: `datalayer/jupyter-mcp-server:latest`
- Multi-architecture support (linux/amd64, linux/arm64)
- Environment-based configuration
- Health check endpoints for orchestration

### Authentication Strategies
1. **Token-based**: Use Jupyter server tokens for authentication
2. **Network-based**: Use network policies for access control
3. **Proxy-based**: Route through authentication proxies
4. **Anonymous**: For development and testing environments
