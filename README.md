# Syntactiq Jupyter MCP Server

A **Model Context Protocol (MCP)** server that provides seamless access to **Jupyter notebooks** for AI agents and LLMs. Built for real-time collaboration, robust execution, and production-grade reliability.

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local development)

### 1. **Start Services**

```bash
# Clone and enter directory
git clone <your-repo>
cd syntactiq-jupyter-mcp

# Quick start (uses .env configuration)
./quick_start.sh
```

### 2. **Configuration**

The server uses `.env` for all configuration. Key settings:

```bash
# Security
JUPYTER_TOKEN=your_secure_token_here

# URLs  
JUPYTER_EXTERNAL_URL=http://localhost:8888
MCP_SERVER_EXTERNAL_URL=http://localhost:4040

# Advanced settings available in .env
```

### 3. **Access Services**

- **JupyterLab**: `http://localhost:8888` (token from `.env`)
- **MCP Server**: `http://localhost:4040`

### 4. **Test Everything**

```bash
# Run comprehensive test suite
python test_suites/mcp_test_suite.py
```

## 🔧 Configuration

All configuration is centralized in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `JUPYTER_TOKEN` | JupyterLab authentication token | `syntactiq_jupyter_mcp_token_2024` |
| `JUPYTER_EXTERNAL_URL` | External JupyterLab URL | `http://localhost:8888` |
| `MCP_SERVER_EXTERNAL_URL` | External MCP server URL | `http://localhost:4040` |
| `TRANSPORT` | MCP transport protocol | `streamable-http` |
| `JUPYTER_COLLABORATIVE` | Enable real-time collaboration | `True` |

**🔐 Security**: Change `JUPYTER_TOKEN` to a secure value for production deployment.

## ⚡ Development

Open `http://localhost:8888?token=<JUPYTER_TOKEN>` in your browser to see real-time changes as your agent interacts with notebooks.

## 🛠 MCP Tools

### **Core Notebook Operations**
