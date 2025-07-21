# 🪐✨ Jupyter MCP Server - Enhanced with Iframe Switching

[![Datalayer](https://assets.datalayer.tech/datalayer-25.svg)](https://datalayer.io)

**Jupyter MCP Server** is a [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server implementation that enables **real-time** interaction with 📓 Jupyter Notebooks, allowing AI to edit, document and execute code for data analysis, visualization etc.

This enhanced version includes **iframe-based notebook switching** for seamless integration into web platforms, plus a comprehensive **multi-user architecture** for production deployments.

## 🎯 Current Implementation: Iframe + MCP Integration

Our implementation combines:
- **MCP Server**: Real-time notebook control via standard Jupyter APIs
- **Iframe Switching**: Seamless notebook navigation in web platforms
- **Synchronized Context**: MCP server follows iframe notebook switches

### Key Features

- ⚡ **Real-time control:** Instantly view notebook changes as they happen
- 🔄 **Iframe Switching:** Switch between notebooks with URL reloading
- 🎯 **Synchronized MCP Context:** MCP operations target the currently displayed notebook  
- 🤝 **MCP-Compatible:** Works with any MCP client (Claude Desktop, Cursor, etc.)
- 🛠️ **Multiple Tools:** `insert_execute_code_cell`, `append_markdown_cell`, `get_notebook_info`, and more

## 🏁 Quick Start

### 1. Start Services

```bash
# Clone and start
git clone <repository>
cd syntactiq-jupyter-mcp
./quick_start.sh
```

### 2. Test Iframe Switching

```bash
# Serve test page via HTTP (required for iframe embedding)
python3 -m http.server 8080 --bind 127.0.0.1 &

# Open in browser
open http://localhost:8080/test_iframe_switching.html
```

### 3. Available Services

- **JupyterLab**: http://localhost:8888 (token: `MY_TOKEN`)
- **MCP Server**: http://localhost:4040
- **Test Interface**: http://localhost:8080/interactive_mcp_test.html

## 🏗️ Architecture

### Current Architecture: Single-User Development

```
┌─────────────────────────────────────────────────────────────────┐
│                    Web Platform / Test Interface                │
│  ┌─────────────────┐                    ┌─────────────────────┐ │
│  │  MCP Controls   │                    │   Jupyter iFrame    │ │
│  │  (buttons/API)  │◄──────────────────►│   (switches on URL) │ │
│  └─────────────────┘                    └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                          │                            │
                     HTTP/MCP                      iframe.src = URL
                          ▼                            ▼
   ┌─────────────────────────────────────────────────────────────┐
   │              Docker Compose Services                        │
   │  ┌─────────────────┐          ┌─────────────────────────┐   │
   │  │  MCP Server     │          │    JupyterLab           │   │
   │  │  :4040          │◄────────►│    :8888                │   │
   │  │                 │ WebSocket│    + Real-time Collab   │   │
   │  └─────────────────┘  RTC API └─────────────────────────┘   │
   └─────────────────────────────────────────────────────────────┘
```

### Key Integration Points

1. **MCP → Jupyter**: Uses standard Jupyter Real-Time Collaboration WebSocket API
2. **Iframe Switching**: URL-based navigation (`/lab/tree/path/to/notebook.ipynb`)
3. **Context Sync**: `prepare_notebook` tool switches MCP server context to match iframe
4. **CSP Configuration**: JupyterLab configured to allow iframe embedding

## 🌐 Multi-User Production Architecture

For production deployments, we designed a scalable multi-user architecture:

### Core Principles
- **One container per user maximum** - complete resource and security isolation
- **Multiple notebooks per user** - within their single container environment  
- **Zero cross-user interaction** - no sharing or collaboration features
- **Platform-only access** - Jupyter instances not directly accessible externally
- **Resource-bounded** - fixed RAM limits with system-wide capacity management
- **On-demand provisioning** - containers created when users first access platform

### Production Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Web Platform (Frontend)                      │
│  ┌─────────────────┐                    ┌─────────────────────┐ │
│  │   Chat/App UI   │                    │   Jupyter iFrame    │ │
│  │                 │◄──────────────────►│   (user-specific)   │ │
│  └─────────────────┘                    └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Platform Backend API                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   Auth Layer    │  │ Container Mgmt  │  │ Resource Monitor│  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Container Orchestration Layer                      │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Nginx Reverse  │  │  Session Store  │  │   Warm Pool     │  │
│  │     Proxy       │  │   (SQLite/Redis)│  │   Manager       │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    User Container Layer                         │
│                                                                 │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────┐ │
│ │   User A        │ │   User B        │ │   User C            │ │
│ │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────────┐ │ │
│ │ │ JupyterLab  │ │ │ │ JupyterLab  │ │ │ │ JupyterLab      │ │ │
│ │ │ :8888       │ │ │ │ :8888       │ │ │ │ :8888           │ │ │
│ │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────────┘ │ │
│ │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────────┐ │ │
│ │ │ MCP Server  │ │ │ │ MCP Server  │ │ │ │ MCP Server      │ │ │
│ │ │ :4040       │ │ │ │ :4040       │ │ │ │ :4040           │ │ │
│ │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────────┘ │ │
│ │ Port: 8001-8002 │ │ Port: 8003-8004 │ │ Port: 8005-8006     │ │
│ └─────────────────┘ └─────────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Production Components

#### 1. Container Management Service

**Responsibilities:**
- Container lifecycle management (create, start, stop, destroy)
- Dynamic port allocation and deallocation  
- Template-based container provisioning
- Resource monitoring and enforcement
- Idle timeout management

#### 2. Resource Management

**Features:**
- **Idle Timeout**: Kill containers after X minutes of inactivity
- **Resource Monitoring**: Alert if user consuming too much RAM
- **Capacity Management**: Monitor available RAM before spawning new containers
- **Overload Protection**: Error response when system overloaded

#### 3. Session Persistence

**SQLite vs Redis Trade-offs:**

| Feature | SQLite | Redis |
|---------|--------|-------|
| **Persistence** | ✅ Durable to disk | ⚠️ Optional persistence |
| **Setup Complexity** | ✅ Zero config | ⚠️ Additional service |
| **Memory Usage** | ✅ Disk-based | ⚠️ RAM-based |
| **Concurrency** | ⚠️ Limited writers | ✅ High concurrency |
| **Expiration** | ❌ Manual cleanup | ✅ Built-in TTL |

**Recommendation**: Start with SQLite for simplicity, migrate to Redis for scale.

#### 4. Advanced Features

- **Dynamic Port Allocation**: Reverse proxy routing by user ID
- **Container Templates**: Different configurations for different use cases  
- **Warm Pool**: Keep pre-warmed containers ready for instant startup
- **Zero Cross-Importing**: Complete isolation between user environments

## 🛠️ Development Tools

### Available Scripts

- **`./quick_start.sh`**: Start development environment
- **`interactive_mcp_test.html`**: Interactive test interface for iframe switching
- **`mcp_test_suite.py`**: Comprehensive automated test suite for all MCP tools
- **`mcp_client.py`**: Python client library for MCP server

### Test Environment

The test interface (`interactive_mcp_test.html`) demonstrates:
- Notebook switching via iframe URL changes
- MCP server context synchronization
- Real-time notebook manipulation (add cells, execute code, etc.)
- Visual feedback for all operations

### MCP Tools Available

- `create_notebook` - Create new notebook files
- `list_notebooks` - List available notebooks
- `prepare_notebook` - Switch MCP context and get iframe URL
- `get_notebook_info` - Get notebook metadata
- `read_all_cells` - Get all cell content
- `append_markdown_cell` - Add markdown cells
- `append_code_cell` - Add code cells  
- `execute_with_progress` - Execute cells with monitoring
- And many more...

## 📝 Configuration

### Development Setup

Our setup uses two different approaches:

**JupyterLab**: Pre-built image with runtime dependency installation
**MCP Server**: Custom-built image with pre-aligned dependencies

```yaml
# docker-compose.yml
services:
  # Uses pre-built Jupyter image with runtime dependency fixes
  jupyterlab:
    image: jupyter/scipy-notebook:latest  # ← Pre-built image
    command: >
      bash -c "pip uninstall -y pycrdt datalayer_pycrdt && 
               pip install datalayer_pycrdt==0.12.17 &&
               jupyter server extension enable --py jupyter_server_ydoc --sys-prefix &&
               jupyter lab --ip 0.0.0.0 --port 8888 
               --IdentityProvider.token=MY_TOKEN
               --ServerApp.tornado_settings='{\"headers\":{\"Content-Security-Policy\":\"frame-ancestors * file: data: blob:\"}}'"

  # Uses our custom Dockerfile with pre-aligned dependencies  
  jupyter-mcp-server:
    build:
      context: .
      # Uses our custom Dockerfile with version fixes
    environment:
      - ROOM_URL=http://jupyterlab:8888
      - ROOM_TOKEN=MY_TOKEN
```

**Why custom Dockerfile for MCP server?**
- Ensures version compatibility between `jupyter-nbmodel-client` and `jupyter_server_ydoc`
- Pre-installs exact dependency versions that work together
- Eliminates runtime compatibility issues

### Production Considerations

- **Load Balancing**: Nginx reverse proxy with user-based routing
- **Resource Limits**: Container memory/CPU limits enforced
- **Security**: No direct external access to Jupyter instances
- **Monitoring**: Resource usage and container health monitoring
- **Backup**: User notebook data persistence and backup strategies

## 🚀 Deployment Options

### 1. Development (Current)
- Single docker-compose with shared JupyterLab + MCP server
- Perfect for testing iframe switching and MCP integration

### 2. Single-User Production  
- One container per user with dedicated JupyterLab + MCP server
- Suitable for small-scale deployments

### 3. Multi-User Production
- Full orchestration layer with container management
- Dynamic provisioning, resource monitoring, warm pools
- Enterprise-scale deployment

## 📚 Further Resources

- **[Original Datalayer Jupyter MCP Server](https://github.com/datalayer/jupyter-mcp-server)**
- **[Model Context Protocol Specification](https://modelcontextprotocol.io)**
- **[JupyterLab Real-Time Collaboration](https://jupyter.org/enhancement-proposals/62-real-time-collaboration/real-time-collaboration.html)**

---

*This enhanced implementation demonstrates the power of combining MCP's standardized protocol with iframe-based integration for seamless notebook control in web platforms.* 🎉
