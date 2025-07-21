# Jupyter MCP Server - Deployment Guide

This directory contains everything you need to deploy and integrate the Jupyter MCP Server with your LLM applications.

## 📋 Files Overview

| File | Purpose |
|------|---------|
| `setup_and_tools.md` | Detailed technical analysis of the MCP server implementation |
| `INTEGRATION_GUIDE.md` | Complete developer integration guide with code examples |
| `docker-compose.yml` | Production-ready Docker Compose setup |
| `.env.example` | Environment configuration template |
| `start.sh` | One-click startup script |

## 🚀 Quick Start

### 1. Automated Setup (Recommended)

```bash
# Make startup script executable and run
chmod +x start.sh
./start.sh
```

This will:
- Create necessary directories and configuration files
- Start JupyterLab and MCP Server
- Create an example notebook
- Verify service health
- Display access information

### 2. Manual Setup

```bash
# Copy environment template
cp .env.example .env

# Edit configuration as needed
nano .env

# Create notebooks directory
mkdir -p notebooks

# Start services
docker-compose up -d

# Check health
curl http://localhost:4040/api/healthz
```

## 🔧 Configuration

### Environment Variables

The `.env` file controls all configuration:

```bash
# Authentication
JUPYTER_TOKEN=your-secure-token-here

# Notebook settings
ROOM_ID=notebook.ipynb
PROVIDER=jupyter

# Server settings
MCP_VERSION=latest
TRANSPORT=streamable-http
PORT=4040
```

### Service URLs

Once running, access services at:

- **JupyterLab**: http://localhost:8888 (token required)
- **MCP Server**: http://localhost:4040
- **Health Check**: http://localhost:4040/api/healthz

## 🛠️ Integration Examples

### HTTP Client

```python
import httpx

async def execute_code(code: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:4040/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "append_execute_code_cell",
                    "arguments": {"cell_source": code}
                }
            }
        )
        return response.json()

# Usage
result = await execute_code("print('Hello from MCP!')")
```

### LangChain Integration

```python
from langchain.tools import BaseTool

class JupyterTool(BaseTool):
    name = "jupyter_execute"
    description = "Execute Python code in Jupyter"
    
    def _run(self, code: str) -> str:
        # Use the HTTP client above
        return execute_code(code)
```

## 🔍 Available MCP Tools

The server provides 12 tools for notebook interaction:

### Information Tools
- `get_notebook_info()` - Get notebook metadata
- `read_all_cells()` - Read all cells
- `read_cell(index)` - Read specific cell

### Creation Tools
- `append_markdown_cell(content)` - Add markdown cell
- `insert_markdown_cell(index, content)` - Insert markdown cell
- `append_execute_code_cell(code)` - Add and execute code
- `insert_execute_code_cell(index, code)` - Insert and execute code

### Modification Tools
- `overwrite_cell_source(index, source)` - Modify cell content
- `delete_cell(index)` - Remove cell

### Execution Tools
- `execute_cell_with_progress(index, timeout)` - Execute with monitoring
- `execute_cell_simple_timeout(index, timeout)` - Simple execution
- `execute_cell_streaming(index, timeout, interval)` - Streaming execution

## 🎯 LLM Agent Prompts

### System Prompt Template

```markdown
You are an AI assistant with access to a live Jupyter notebook environment.

Available Tools:
- Read notebook structure and cells
- Execute Python code with real-time feedback
- Add documentation and explanations
- Modify and organize notebook content

Best Practices:
1. Start by examining the notebook structure
2. Add markdown documentation for complex analysis
3. Use meaningful variable names and comments
4. Handle errors gracefully with explanations
5. Use progress monitoring for long-running tasks

Workflow:
1. Import necessary libraries
2. Load and explore data
3. Document findings with markdown
4. Perform analysis step by step
5. Visualize results
6. Summarize conclusions
```

### Data Analysis Prompt

```markdown
You are a data analyst with Jupyter access. For any dataset:

1. **Explore**: Check shape, types, missing values
2. **Clean**: Handle data quality issues
3. **Analyze**: Create visualizations and statistics
4. **Document**: Explain findings in markdown
5. **Recommend**: Provide actionable insights

Always explain your methodology and document your reasoning.
```

## 🔧 Management Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Restart specific service
docker-compose restart jupyter-mcp-server

# Update to latest version
docker-compose pull
docker-compose up -d

# Clean up everything
docker-compose down -v --remove-orphans
```

## 🏗️ Production Deployment

### Enable Production Profile

```bash
# Use production profile with nginx proxy
export COMPOSE_PROFILES=production
docker-compose up -d
```

### Scaling Profile

```bash
# Enable Redis for session management
export COMPOSE_PROFILES=scaling
docker-compose up -d
```

### Kubernetes Deployment

See `INTEGRATION_GUIDE.md` for complete Kubernetes manifests and configuration.

## 🔒 Security Considerations

### Token Security

- Use strong, unique tokens for production
- Rotate tokens regularly
- Store tokens securely (environment variables, secrets)

### Network Security

- Use HTTPS/TLS in production
- Configure firewall rules appropriately
- Consider VPN access for sensitive environments

### Container Security

- Keep Docker images updated
- Use non-root users where possible
- Limit container privileges

## 🐛 Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| Port already in use | Change ports in `.env` file |
| Permission denied | Check Docker permissions |
| Connection refused | Verify services are running |
| Token mismatch | Check token consistency |

### Debug Mode

```bash
# Enable verbose logging
docker-compose logs -f jupyter-mcp-server

# Check service health
curl http://localhost:4040/api/healthz

# Test MCP connection
curl -X POST http://localhost:4040/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## 📊 Monitoring

### Health Checks

Services include built-in health checks:

```bash
# Check all services
docker-compose ps

# Manual health verification
curl http://localhost:8888/api
curl http://localhost:4040/api/healthz
```

### Logs

```bash
# View all logs
docker-compose logs

# Follow specific service
docker-compose logs -f jupyter-mcp-server

# Get last 100 lines
docker-compose logs --tail=100
```

## 🤝 Contributing

When modifying the deployment:

1. Test with different configurations
2. Update documentation accordingly
3. Verify security implications
4. Test upgrade/downgrade paths
5. Document breaking changes

## 📚 Additional Resources

- **Technical Details**: See `setup_and_tools.md`
- **Integration Guide**: See `INTEGRATION_GUIDE.md`
- **Project Documentation**: https://jupyter-mcp-server.datalayer.tech/
- **Model Context Protocol**: https://modelcontextprotocol.io

## 🆘 Support

For issues and questions:

1. Check this documentation first
2. Review the troubleshooting section
3. Check existing GitHub issues
4. Create a new issue with detailed information

---

**Happy coding with Jupyter MCP Server! 🪐✨** 