# Jupyter MCP Server - Version Compatibility Solution

## 🎯 Problem Solved

**Issue**: `jupyter-nbmodel-client 0.13.5` (in MCP server container) was incompatible with `jupyter_server_ydoc 2.1.0` (in JupyterLab container), causing:
- `404 GET /api/collaboration/room` errors
- `ModuleNotFoundError: No module named 'jupyter_server.contents'`
- MCP server unable to connect to notebook collaboration sessions

## ✅ Root Cause Analysis

1. **Version Mismatch**: Different containers had incompatible package versions
2. **API Breaking Changes**: Jupyter collaboration APIs changed between versions
3. **Package Conflicts**: `pycrdt` vs `datalayer_pycrdt` version conflicts
4. **Extension State**: `jupyter_server_ydoc` was loaded but not enabled as a server extension

## 🛠️ Complete Solution

### 1. Custom MCP Server Container (`Dockerfile.custom`)

Created a version-aligned MCP server that matches JupyterLab's package versions:

```dockerfile
# Align package versions to match our JupyterLab setup
RUN pip install --force-reinstall \
    jupyterlab==4.4.1 \
    jupyter-collaboration==4.0.2 \
    jupyter-server-ydoc==2.1.0 \
    ipykernel

# Handle pycrdt compatibility the same way as our JupyterLab container
RUN pip uninstall -y pycrdt datalayer_pycrdt || true
RUN pip install datalayer_pycrdt==0.12.17

# Ensure exact same jupyter-nbmodel-client version
RUN pip install --force-reinstall jupyter-nbmodel-client==0.13.5
```

### 2. Updated Docker Compose Configuration

Modified `docker-compose.yml` to build custom MCP server:

```yaml
jupyter-mcp-server:
  build:
    context: .
    dockerfile: Dockerfile.custom
  # ... rest of config
```

### 3. JupyterLab Extension Enablement

Ensured `jupyter_server_ydoc` is properly enabled as a server extension:

```bash
jupyter server extension enable --py jupyter_server_ydoc --sys-prefix
```

### 4. Correct MCP Endpoint

Fixed MCP endpoint URL (removed trailing slash):
- ❌ Wrong: `http://localhost:4040/mcp/` → `307 Temporary Redirect`
- ✅ Correct: `http://localhost:4040/mcp` → Works perfectly

## 🧪 Testing & Validation

### Automated Test Script (`test_version_fix.sh`)

Comprehensive testing that validates:
- Custom image build
- Service health checks
- Collaboration API availability
- Package version alignment
- MCP tool functionality

### Manual Verification Commands

```bash
# 1. Check collaboration API
curl "http://localhost:8888/api/collaboration/room?token=MY_TOKEN"

# 2. List MCP tools
curl -X POST "http://localhost:4040/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'

# 3. Test notebook info
curl -X POST "http://localhost:4040/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", 
       "params": {"name": "get_notebook_info", "arguments": {}}}'

# 4. Execute code
curl -X POST "http://localhost:4040/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
       "params": {"name": "append_execute_code_cell", 
                  "arguments": {"cell_source": "print(\"Hello MCP!\")"}}}'
```

## 📊 Results Achieved

### ✅ JupyterLab Container
- `jupyter_server_ydoc 2.1.0` ✅ enabled
- `jupyter-collaboration 4.0.2` ✅ installed  
- `datalayer_pycrdt==0.12.17` ✅ installed
- Collaboration rooms working ✅
- Extension properly enabled ✅

### ✅ MCP Server Container  
- `jupyter-nbmodel-client 0.13.5` ✅ compatible
- `jupyter_server_ydoc 2.1.0` ✅ aligned
- `datalayer_pycrdt==0.12.17` ✅ aligned
- All 12 MCP tools available ✅
- Code execution working ✅

### ✅ Integration Tests
- **Health checks**: Both services healthy
- **Tool listing**: All 12 tools available
- **Notebook info**: `{"room_id": "notebook.ipynb", "total_cells": 7, "cell_types": {"markdown": 2, "code": 5}}`
- **Code execution**: `"🎉 MCP server is working!\nCurrent time: 2025-07-21 11:39:05.416193\n2 + 2 = 4"`

## 🎯 Key Learnings

1. **Version Alignment is Critical**: Both containers must use identical Jupyter collaboration package versions
2. **Extension vs Server Extension**: Extensions can be loaded but not enabled - server extensions must be explicitly enabled
3. **MCP Endpoint Format**: Use `/mcp` not `/mcp/` to avoid redirects
4. **pycrdt Compatibility**: Use `datalayer_pycrdt==0.12.17` for Datalayer's MCP server
5. **Custom Docker Builds**: Sometimes necessary to ensure version compatibility across services

## 🚀 Production Deployment

For production use:

1. **Use the custom Dockerfile.custom** for the MCP server
2. **Version pin all Jupyter packages** in both containers
3. **Monitor package updates** and test compatibility before upgrading
4. **Use the validated docker-compose.yml** configuration
5. **Run test_version_fix.sh** before each deployment

## 📋 Quick Start

```bash
# 1. Stop existing containers
docker-compose down

# 2. Build custom MCP server
docker-compose build jupyter-mcp-server

# 3. Start services
docker-compose up -d

# 4. Verify functionality
./test_version_fix.sh

# 5. Open JupyterLab and test
# - Open: http://localhost:8888?token=MY_TOKEN
# - Open notebook.ipynb
# - Run: python test_mcp_demo.py
```

## 🔧 Troubleshooting

If issues persist:

1. **Check extension status**: `docker exec jupyter-mcp-jupyterlab jupyter server extension list`
2. **Compare package versions**: `docker exec <container> pip list | grep jupyter`
3. **Test endpoints individually**: Use the manual verification commands above
4. **Check logs**: `docker-compose logs <service-name>`

The version alignment approach ensures robust, reliable Jupyter MCP Server operation with full real-time collaboration support. 