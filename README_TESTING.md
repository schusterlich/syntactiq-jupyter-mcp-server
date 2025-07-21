# 🧪 Local Testing Setup

Quick start guide for testing the Jupyter MCP Server locally.

## Files Created for Testing

| File | Purpose |
|------|---------|
| `test_mcp_demo.py` | 🎯 **Comprehensive demo script** - Tests all MCP tools with real examples |
| `quick_start.sh` | ⚡ **Fast startup** - Just launches services without demo |
| `requirements-demo.txt` | 📦 **Dependencies** - Python packages for demo script |
| `TESTING_GUIDE.md` | 📖 **Detailed guide** - Complete testing instructions |
| `notebooks/notebook.ipynb` | 📓 **Demo notebook** - Default notebook for MCP server |

## Two Ways to Test

### 🚀 Option 1: Quick Start (Services Only)
```bash
./quick_start.sh
```
- Starts JupyterLab (port 8888) and MCP Server (port 4040)
- Shows service URLs and management commands
- Manual testing with browser or curl

### 🎯 Option 2: Full Demo (Recommended)
```bash
pip install -r requirements-demo.txt
python test_mcp_demo.py
```
- Automatically starts services
- **Prompts you to open the notebook in JupyterLab** (required for MCP connection)
- Tests all 12 MCP tools with real examples
- Shows live notebook interaction
- Demonstrates code execution, cell creation, progress monitoring

## What You'll See Working

✅ **Real-time notebook control** - AI can read/write/execute notebook cells  
✅ **Code execution** - Python code runs and outputs are captured  
✅ **Progress monitoring** - Long-running tasks show real-time progress  
✅ **Cell management** - Add/modify/delete markdown and code cells  
✅ **MCP protocol** - JSON-RPC communication over HTTP  
✅ **Health monitoring** - Service status and error handling  
✅ **Live collaboration** - Watch cells appear in JupyterLab as the demo runs!  

## Access URLs

- **JupyterLab**: http://localhost:8888?token=MY_TOKEN
- **MCP Server**: http://localhost:4040
- **Health Check**: http://localhost:4040/api/healthz

## 📝 Important Notes

- **📓 Notebook must be open**: The MCP server requires an active JupyterLab session
- **🔄 Real-time sync**: Changes appear instantly in both the demo and JupyterLab
- **⚡ Live collaboration**: This demonstrates how AI agents work with active notebooks

## Next Steps

After testing locally:
1. ✅ Verify MCP tools work as expected
2. 🔧 Integrate with your LLM application using the HTTP API
3. 🏗️ Implement multi-user architecture from `ARCHITECTURE_SPECIFICATION.md`
4. 🚀 Deploy to production with container-per-user strategy

## Quick Commands

```bash
# Start services
./quick_start.sh

# Run full demo
python test_mcp_demo.py

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Check health
curl http://localhost:4040/api/healthz
```

This setup demonstrates the core functionality you need for AI-notebook integration! 🪐✨ 