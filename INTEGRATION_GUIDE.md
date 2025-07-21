# Jupyter MCP Server - Developer Integration Guide

## Overview

This guide helps developers integrate the Jupyter MCP Server into their LLM applications, providing real-time Jupyter notebook interaction capabilities for AI agents.

## Quick Start

### 1. Using Docker Compose (Recommended)

```bash
# Clone or copy the docker-compose.yml to your project
cp docker-compose.yml your-project/
cd your-project/

# Create notebooks directory
mkdir -p notebooks

# Create environment file (optional)
cat > .env << EOF
JUPYTER_TOKEN=your-secure-token-here
PROVIDER=jupyter
ROOM_ID=analysis.ipynb
MCP_VERSION=latest
EOF

# Start services
docker-compose up -d

# Check health
curl http://localhost:4040/api/healthz
curl http://localhost:8888/api
```

### 2. Manual Setup

```bash
# Start JupyterLab
pip install jupyterlab==4.4.1 jupyter-collaboration==4.0.2 ipykernel
pip uninstall -y pycrdt datalayer_pycrdt
pip install datalayer_pycrdt==0.12.17
jupyter lab --port 8888 --IdentityProvider.token MY_TOKEN

# Start MCP Server (in another terminal)
docker run -d \
  -p 4040:4040 \
  -e TRANSPORT=streamable-http \
  -e ROOM_URL=http://host.docker.internal:8888 \
  -e ROOM_TOKEN=MY_TOKEN \
  -e ROOM_ID=notebook.ipynb \
  -e RUNTIME_URL=http://host.docker.internal:8888 \
  -e RUNTIME_TOKEN=MY_TOKEN \
  datalayer/jupyter-mcp-server:latest
```

## Integration Patterns

### 1. HTTP API Integration

The MCP server exposes a REST API when using `streamable-http` transport:

```python
import httpx
import json

class JupyterMCPClient:
    def __init__(self, base_url: str = "http://localhost:4040"):
        self.base_url = base_url
        self.client = httpx.Client()
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool via HTTP"""
        response = await self.client.post(
            f"{self.base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
        )
        return response.json()
    
    async def get_notebook_info(self) -> dict:
        """Get basic notebook information"""
        return await self.call_tool("get_notebook_info", {})
    
    async def execute_code(self, code: str) -> list[str]:
        """Execute code in a new cell"""
        return await self.call_tool("append_execute_code_cell", {
            "cell_source": code
        })

# Usage example
client = JupyterMCPClient()
info = await client.get_notebook_info()
result = await client.execute_code("print('Hello from MCP!')")
```

### 2. MCP Client Integration

For direct MCP protocol integration:

```python
import asyncio
from mcp import Client
from mcp.client.sse import SseSession

async def main():
    async with SseSession("http://localhost:4040/mcp") as session:
        client = Client(session)
        
        # Initialize connection
        await client.initialize()
        
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {[tool.name for tool in tools]}")
        
        # Execute code
        result = await client.call_tool(
            "append_execute_code_cell",
            {"cell_source": "import pandas as pd\nprint(pd.__version__)"}
        )
        print(f"Execution result: {result}")

asyncio.run(main())
```

### 3. LangChain Integration

```python
from langchain.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

class JupyterExecuteTool(BaseTool):
    name = "jupyter_execute"
    description = "Execute Python code in a Jupyter notebook"
    
    class InputSchema(BaseModel):
        code: str = Field(description="Python code to execute")
    
    args_schema: Type[BaseModel] = InputSchema
    
    def __init__(self, mcp_client):
        super().__init__()
        self.mcp_client = mcp_client
    
    def _run(self, code: str) -> str:
        result = asyncio.run(self.mcp_client.execute_code(code))
        return "\n".join(result)
    
    async def _arun(self, code: str) -> str:
        result = await self.mcp_client.execute_code(code)
        return "\n".join(result)

# Usage with LangChain agent
from langchain.agents import initialize_agent, AgentType
from langchain.llms import OpenAI

tools = [JupyterExecuteTool(client)]
agent = initialize_agent(
    tools,
    OpenAI(temperature=0),
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

response = agent.run("Calculate the mean of the list [1, 2, 3, 4, 5] using pandas")
```

## LLM Agent Prompts

### System Prompt for Jupyter-Enabled Agents

```markdown
You are an AI assistant with access to a live Jupyter notebook environment. You can:

1. **Read & Analyze**: Use `read_all_cells()` or `read_cell()` to examine existing code and outputs
2. **Execute Code**: Use `append_execute_code_cell()` for new analysis or `execute_cell_with_progress()` for long-running tasks
3. **Document Work**: Use `append_markdown_cell()` to add explanations and insights
4. **Iterate**: Use `overwrite_cell_source()` to refine code based on results

**Available Tools:**
- `get_notebook_info()`: Get notebook metadata and structure
- `read_all_cells()`: Read all cells in the notebook
- `read_cell(index)`: Read a specific cell
- `append_execute_code_cell(code)`: Add and execute new code
- `insert_execute_code_cell(index, code)`: Insert code at specific position
- `execute_cell_with_progress(index, timeout)`: Execute with progress monitoring
- `append_markdown_cell(content)`: Add documentation
- `overwrite_cell_source(index, source)`: Modify existing cells
- `delete_cell(index)`: Remove cells

**Best Practices:**
1. Start by examining the notebook with `get_notebook_info()` and `read_all_cells()`
2. Add markdown documentation before complex analysis
3. Use meaningful variable names and comments
4. Handle errors gracefully and provide explanations
5. For long-running tasks, use `execute_cell_with_progress()` with appropriate timeouts

**Data Analysis Workflow:**
1. Import necessary libraries
2. Load and explore data
3. Document findings with markdown cells
4. Perform analysis step by step
5. Visualize results
6. Summarize conclusions
```

### Task-Specific Prompts

#### Data Analysis Assistant
```markdown
You are a data analysis expert with access to a Jupyter environment. When given a dataset:

1. **Initial Exploration**: Load data, check shape, dtypes, missing values
2. **Data Quality**: Identify and document data quality issues
3. **Exploratory Analysis**: Create visualizations and summary statistics
4. **Insights**: Document key findings in markdown cells
5. **Recommendations**: Provide actionable insights

Always explain your code and findings in markdown cells for clarity.
```

#### Machine Learning Assistant
```markdown
You are an ML engineer with Jupyter access. For ML tasks:

1. **Data Preparation**: Load, clean, and preprocess data
2. **Feature Engineering**: Create and select relevant features
3. **Model Training**: Train and validate models with proper cross-validation
4. **Evaluation**: Generate comprehensive performance metrics
5. **Visualization**: Create plots showing model performance
6. **Documentation**: Explain methodology and results

Use `execute_cell_with_progress()` for training long-running models.
```

#### Code Review Assistant
```markdown
You are a code reviewer with Jupyter access. When reviewing notebooks:

1. **Structure Analysis**: Examine overall notebook organization
2. **Code Quality**: Check for best practices, readability, efficiency
3. **Output Validation**: Verify that outputs match expected results
4. **Documentation**: Ensure adequate comments and markdown explanations
5. **Suggestions**: Provide specific improvement recommendations

Use `read_all_cells()` to get full context before providing feedback.
```

## Configuration Examples

### Environment Variables

```bash
# Basic configuration
JUPYTER_TOKEN=your-secure-token
PROVIDER=jupyter
ROOM_ID=analysis.ipynb
TRANSPORT=streamable-http
PORT=4040

# Runtime configuration
RUNTIME_URL=http://localhost:8888
START_NEW_RUNTIME=true
RUNTIME_TOKEN=your-secure-token

# Room configuration
ROOM_URL=http://localhost:8888
ROOM_TOKEN=your-secure-token
```

### Dynamic Configuration via API

```python
import httpx

async def configure_mcp_server(config: dict):
    """Dynamically configure MCP server connection"""
    async with httpx.AsyncClient() as client:
        response = await client.put(
            "http://localhost:4040/api/connect",
            json={
                "provider": config.get("provider", "jupyter"),
                "room_url": config["room_url"],
                "room_id": config["room_id"],
                "room_token": config["room_token"],
                "runtime_url": config["runtime_url"],
                "runtime_id": config.get("runtime_id"),
                "runtime_token": config["runtime_token"]
            }
        )
        return response.json()

# Example usage
config = {
    "provider": "jupyter",
    "room_url": "http://localhost:8888",
    "room_id": "data_analysis.ipynb",
    "room_token": "MY_TOKEN",
    "runtime_url": "http://localhost:8888",
    "runtime_token": "MY_TOKEN"
}

result = await configure_mcp_server(config)
```

## Error Handling

### Common Issues and Solutions

```python
class JupyterMCPError(Exception):
    pass

async def robust_code_execution(client, code: str, max_retries: int = 3):
    """Execute code with error handling and retries"""
    for attempt in range(max_retries):
        try:
            result = await client.execute_code(code)
            
            # Check for execution errors in output
            if any("Error" in output or "Exception" in output for output in result):
                raise JupyterMCPError(f"Execution error: {result}")
            
            return result
            
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise JupyterMCPError("Execution timed out after retries")
        
        except httpx.ConnectError:
            raise JupyterMCPError("Cannot connect to MCP server")
        
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            raise JupyterMCPError(f"Unexpected error: {e}")

# Usage
try:
    result = await robust_code_execution(client, "print('Hello')")
except JupyterMCPError as e:
    print(f"Execution failed: {e}")
```

## Monitoring and Logging

### Health Checks

```python
import asyncio
import logging

async def monitor_mcp_server(base_url: str, interval: int = 30):
    """Monitor MCP server health"""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                response = await client.get(f"{base_url}/api/healthz")
                health = response.json()
                
                if health.get("status") != "healthy":
                    logging.warning(f"MCP server unhealthy: {health}")
                else:
                    logging.info(f"MCP server healthy - kernel: {health.get('kernel_status')}")
                    
            except Exception as e:
                logging.error(f"Health check failed: {e}")
            
            await asyncio.sleep(interval)

# Start monitoring
asyncio.create_task(monitor_mcp_server("http://localhost:4040"))
```

### Logging Configuration

```python
import logging

# Configure logging for MCP integration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('jupyter_mcp.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('jupyter_mcp_client')

# Log all tool calls
async def logged_tool_call(client, tool_name: str, arguments: dict):
    logger.info(f"Calling tool: {tool_name} with args: {arguments}")
    try:
        result = await client.call_tool(tool_name, arguments)
        logger.info(f"Tool result: {result}")
        return result
    except Exception as e:
        logger.error(f"Tool call failed: {e}")
        raise
```

## Security Considerations

### Token Management

```python
import os
from cryptography.fernet import Fernet

class SecureTokenManager:
    def __init__(self, key_file: str = ".mcp_key"):
        self.key_file = key_file
        self.key = self._load_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _load_or_create_key(self) -> bytes:
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            os.chmod(self.key_file, 0o600)  # Secure permissions
            return key
    
    def encrypt_token(self, token: str) -> str:
        return self.cipher.encrypt(token.encode()).decode()
    
    def decrypt_token(self, encrypted_token: str) -> str:
        return self.cipher.decrypt(encrypted_token.encode()).decode()

# Usage
token_manager = SecureTokenManager()
encrypted_token = token_manager.encrypt_token("MY_SECURE_TOKEN")
```

### Network Security

```python
# Use SSL/TLS in production
import ssl

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False  # Only for development
ssl_context.verify_mode = ssl.CERT_NONE  # Only for development

async with httpx.AsyncClient(verify=ssl_context) as client:
    response = await client.get("https://your-mcp-server:4040/api/healthz")
```

## Production Deployment

### Kubernetes Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jupyter-mcp-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: jupyter-mcp-server
  template:
    metadata:
      labels:
        app: jupyter-mcp-server
    spec:
      containers:
      - name: mcp-server
        image: datalayer/jupyter-mcp-server:latest
        ports:
        - containerPort: 4040
        env:
        - name: TRANSPORT
          value: "streamable-http"
        - name: ROOM_URL
          value: "http://jupyterlab-service:8888"
        - name: RUNTIME_URL
          value: "http://jupyterlab-service:8888"
        - name: JUPYTER_TOKEN
          valueFrom:
            secretKeyRef:
              name: jupyter-secrets
              key: token
        livenessProbe:
          httpGet:
            path: /api/healthz
            port: 4040
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/healthz
            port: 4040
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: jupyter-mcp-service
spec:
  selector:
    app: jupyter-mcp-server
  ports:
  - port: 4040
    targetPort: 4040
```

### Load Balancing

For high-availability deployments, consider:

1. **Stateless Operations**: Most MCP tools are stateless except for kernel connections
2. **Session Affinity**: Use sticky sessions if maintaining kernel state
3. **Health Checks**: Implement proper health monitoring
4. **Graceful Shutdown**: Allow active executions to complete

## Troubleshooting

### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Connection refused | `httpx.ConnectError` | Check if MCP server is running |
| Authentication failure | 401/403 errors | Verify tokens match |
| Kernel not starting | Timeout on execution | Check Jupyter server accessibility |
| WebSocket errors | Connection closed errors | Verify network connectivity |
| Output not syncing | Missing execution results | Use `execute_cell_with_progress` |

### Debug Mode

```python
import logging
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("jupyter_mcp_server").setLevel(logging.DEBUG)

# Enable verbose MCP protocol logging
client = JupyterMCPClient(debug=True)
```

## Contributing

When developing integrations:

1. **Test thoroughly** with different notebook states
2. **Handle edge cases** like empty notebooks, long executions
3. **Document** your integration patterns
4. **Follow security** best practices for token handling
5. **Contribute back** improvements and fixes

For questions and support, refer to the [project documentation](https://jupyter-mcp-server.datalayer.tech/) or open an issue on GitHub. 