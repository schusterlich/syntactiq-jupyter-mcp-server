# Testing Jupyter MCP Server Locally

This guide helps you test the Jupyter MCP Server locally using the provided scripts.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.8+ (for the demo script)

## Quick Start (Just Launch Services)

```bash
# Make script executable (if not already)
chmod +x quick_start.sh

# Start services
./quick_start.sh
```

This will:
- Start JupyterLab on port 8888
- Start MCP Server on port 4040
- Check health of both services
- Show you access URLs

## Full Demo (Recommended)

```bash
# Install Python dependencies
pip install -r requirements-demo.txt

# Run the comprehensive demo
python test_mcp_demo.py
```

This will:
- Start all services automatically
- Wait for them to be healthy
- Create a demo notebook
- Test all MCP tools with real examples:
  - Get notebook info
  - Read cells
  - Add markdown cells
  - Execute Python code
  - Show long-running task execution
- Show final results and access information

## What You'll See

The demo tests these MCP tools:
- `get_notebook_info()` - Get notebook metadata
- `read_all_cells()` - Read all cells
- `append_markdown_cell()` - Add documentation
- `append_execute_code_cell()` - Execute Python code
- Real-time code execution with output

## Access URLs

After starting:
- **JupyterLab**: http://localhost:8888?token=MY_TOKEN
- **MCP Server**: http://localhost:4040
- **Health Check**: http://localhost:4040/api/healthz

## Manual Testing

You can also test MCP tools manually using curl:

```bash
# List available tools
curl -X POST http://localhost:4040/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# Get notebook info
curl -X POST http://localhost:4040/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_notebook_info",
      "arguments": {}
    }
  }'

# Execute code
curl -X POST http://localhost:4040/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "append_execute_code_cell",
      "arguments": {
        "cell_source": "print(\"Hello from MCP!\")\nimport datetime\nprint(f\"Current time: {datetime.datetime.now()}\")"
      }
    }
  }'
```

## Stopping Services

```bash
docker-compose down
```

## Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f jupyter-mcp-server
docker-compose logs -f jupyterlab
```

## Troubleshooting

### Services not starting
- Check if ports 8888 and 4040 are available
- Run `docker-compose down` first to clean up
- Check Docker daemon is running

### MCP Server connection errors
- Wait a bit longer for services to fully start
- Check health endpoint: `curl http://localhost:4040/api/healthz`
- Verify JupyterLab is accessible: `curl http://localhost:8888/api`

### Python script errors
- Install dependencies: `pip install -r requirements-demo.txt`
- Check Python version is 3.8+
- Make sure services are running first

## What This Tests

✅ **Real-time notebook interaction**  
✅ **Code execution with output capture**  
✅ **Markdown cell creation**  
✅ **Notebook structure reading**  
✅ **MCP protocol over HTTP**  
✅ **Service health monitoring**  
✅ **WebSocket connections for live updates**

This demonstrates the core functionality you'll need for integrating AI agents with Jupyter notebooks! 