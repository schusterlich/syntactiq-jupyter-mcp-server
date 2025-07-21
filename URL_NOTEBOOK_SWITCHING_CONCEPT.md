# URL-Based Notebook Switching for MCP Server

## 🎯 **Core Concept**

Instead of programmatic tab control, use **URL-based navigation** with workspace management to achieve the same user experience.

## 🏗️ **Architecture**

### **1. Conversation-to-Workspace Mapping**
```python
# Each conversation gets its own workspace
conversation_id = "conv_2024_01_15_analysis"
workspace_name = f"workspace_{conversation_id}"
notebook_path = f"conversations/{conversation_id}.ipynb"
```

### **2. Enhanced MCP Server URLs**
```python
def create_switch_notebook_url(notebook_path: str, conversation_id: str) -> str:
    """Create URL that switches to specific notebook and closes others"""
    
    # Option A: Use reset parameter (closes all other tabs)
    base_url = f"http://localhost:8888/lab/tree/{notebook_path}"
    return f"{base_url}?reset&token={JUPYTER_TOKEN}"
    
    # Option B: Use named workspace with reset
    workspace = f"conv_{conversation_id}"
    return f"http://localhost:8888/lab/workspaces/{workspace}/tree/{notebook_path}?reset&token={JUPYTER_TOKEN}"

def create_focused_workspace_url(conversation_id: str) -> str:
    """Create a focused workspace for this conversation"""
    workspace = f"conv_{conversation_id}"
    return f"http://localhost:8888/lab/workspaces/{workspace}?reset&token={JUPYTER_TOKEN}"
```

### **3. New MCP Tool: `switch_notebook`**
```python
@server.tool()
async def switch_notebook(notebook_path: str, conversation_id: str) -> str:
    """
    Switch to a specific notebook and close all other tabs.
    Returns a URL that the client should navigate to.
    """
    
    # Ensure notebook exists
    if not await notebook_exists(notebook_path):
        await create_notebook(notebook_path)
    
    # Update MCP server context
    global ROOM_ID
    ROOM_ID = notebook_path
    
    # Create switch URL with reset
    switch_url = create_switch_notebook_url(notebook_path, conversation_id)
    
    return {
        "action": "navigate_to_url",
        "url": switch_url,
        "message": f"Navigate to this URL to switch to {notebook_path}",
        "auto_close_others": True  # ?reset parameter handles this
    }
```

### **4. Enhanced `prepare_notebook` Tool**
```python
@server.tool()
async def prepare_notebook(
    notebook_path: str, 
    conversation_id: str,
    auto_switch: bool = True
) -> dict:
    """
    Comprehensive notebook preparation with optional auto-switching.
    """
    
    # Create notebook if needed
    if not await notebook_exists(notebook_path):
        await create_notebook(notebook_path)
        
    # Switch MCP context
    global ROOM_ID
    ROOM_ID = notebook_path
    
    # Create switching URL
    switch_url = create_switch_notebook_url(notebook_path, conversation_id)
    
    result = {
        "notebook_path": notebook_path,
        "notebook_ready": True,
        "mcp_context_switched": True,
        "switch_url": switch_url,
        "workspace": f"conv_{conversation_id}"
    }
    
    if auto_switch:
        result["action"] = "navigate_to_url"
        result["url"] = switch_url
        result["message"] = "Automatically switching to notebook..."
    
    return result
```

## 🔗 **Client Integration Options**

### **Option 1: HTTP Redirect Response**
```python
from fastapi.responses import RedirectResponse

@server.endpoint("/switch-notebook")
async def switch_notebook_endpoint(notebook_path: str, conversation_id: str):
    """HTTP endpoint that redirects browser to target notebook"""
    
    switch_url = create_switch_notebook_url(notebook_path, conversation_id)
    
    # Update MCP context
    global ROOM_ID
    ROOM_ID = notebook_path
    
    # Redirect browser
    return RedirectResponse(url=switch_url, status_code=307)
```

### **Option 2: WebSocket Message with URL**
```python
# MCP server sends message with URL
{
    "action": "navigate_to_url",
    "url": "http://localhost:8888/lab/tree/conversations/conv_123.ipynb?reset&token=...",
    "reason": "switch_notebook",
    "conversation_id": "conv_123"
}

# Client handles navigation
if (message.action === "navigate_to_url") {
    window.location.href = message.url;  // Forces browser navigation
}
```

### **Option 3: Server-Sent Events (SSE)**
```python
async def send_navigation_event(notebook_path: str, conversation_id: str):
    """Send SSE event to trigger browser navigation"""
    
    switch_url = create_switch_notebook_url(notebook_path, conversation_id)
    
    event_data = {
        "type": "notebook_switch",
        "url": switch_url,
        "conversation_id": conversation_id,
        "timestamp": time.time()
    }
    
    # Send to SSE stream
    yield f"event: navigate\ndata: {json.dumps(event_data)}\n\n"
```

## ⚡ **Enhanced User Experience**

### **1. Conversation Management**
```python
@server.tool()
async def create_conversation_notebook(
    conversation_id: str,
    title: str = None,
    template: str = "default"
) -> dict:
    """Create a new conversation notebook with automatic switching"""
    
    notebook_path = f"conversations/{conversation_id}.ipynb"
    
    # Create notebook with conversation-specific content
    await create_notebook_with_template(notebook_path, template, {
        "conversation_id": conversation_id,
        "title": title or f"Conversation {conversation_id}",
        "created": datetime.now().isoformat()
    })
    
    # Auto-switch to new notebook
    return await prepare_notebook(notebook_path, conversation_id, auto_switch=True)

@server.tool()
async def list_conversation_notebooks() -> list:
    """List all conversation notebooks with switching URLs"""
    
    notebooks = await list_notebooks_in_directory("conversations/")
    
    result = []
    for nb in notebooks:
        conversation_id = extract_conversation_id(nb.path)
        switch_url = create_switch_notebook_url(nb.path, conversation_id)
        
        result.append({
            "path": nb.path,
            "conversation_id": conversation_id,
            "switch_url": switch_url,
            "last_modified": nb.last_modified,
            "is_current": nb.path == ROOM_ID
        })
    
    return result
```

### **2. Smart Workspace Management**
```python
async def cleanup_old_workspaces():
    """Clean up unused conversation workspaces"""
    
    # Get all workspaces
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{JUPYTER_URL}/lab/api/workspaces/")
        workspaces = response.json()
    
    # Remove old conversation workspaces
    for workspace_id in workspaces.get("workspaces", {}).get("ids", []):
        if workspace_id.startswith("conv_") and is_workspace_old(workspace_id):
            await client.delete(f"{JUPYTER_URL}/lab/api/workspaces/{workspace_id}")

async def create_clean_workspace(conversation_id: str):
    """Create a clean workspace for conversation"""
    
    workspace_name = f"conv_{conversation_id}"
    workspace_data = {
        "data": {},  # Empty workspace
        "metadata": {
            "id": f"/lab/workspaces/{workspace_name}",
            "conversation_id": conversation_id,
            "created": datetime.now().isoformat()
        }
    }
    
    async with httpx.AsyncClient() as client:
        await client.put(
            f"{JUPYTER_URL}/lab/api/workspaces/{workspace_name}",
            json=workspace_data
        )
```

## 🎯 **Client Implementation**

### **Simple JavaScript Client**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Notebook Manager</title>
</head>
<body>
    <div id="notebook-container">
        <!-- Hidden iframe for invisible operation -->
        <iframe id="jupyter-frame" 
                src="http://localhost:8888/lab" 
                style="width: 0; height: 0; border: none;">
        </iframe>
    </div>
    
    <script>
        class NotebookManager {
            constructor() {
                this.mcpWebSocket = new WebSocket('ws://localhost:4040/mcp');
                this.setupEventHandlers();
            }
            
            setupEventHandlers() {
                this.mcpWebSocket.onmessage = (event) => {
                    const message = JSON.parse(event.data);
                    
                    if (message.action === 'navigate_to_url') {
                        this.switchToNotebook(message.url);
                    }
                };
            }
            
            switchToNotebook(url) {
                // Option 1: Update iframe src (invisible mode)
                document.getElementById('jupyter-frame').src = url;
                
                // Option 2: Full browser navigation (visible mode)
                // window.location.href = url;
                
                // Option 3: Open in new tab (multi-tab mode)
                // window.open(url, '_blank');
            }
            
            async createConversation(title) {
                const response = await fetch('http://localhost:4040/mcp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tool: 'create_conversation_notebook',
                        arguments: {
                            conversation_id: `conv_${Date.now()}`,
                            title: title
                        }
                    })
                });
                
                const result = await response.json();
                if (result.action === 'navigate_to_url') {
                    this.switchToNotebook(result.url);
                }
            }
        }
        
        // Initialize
        const manager = new NotebookManager();
    </script>
</body>
</html>
```

## ✅ **Advantages of This Approach**

1. **No Extension Required**: Works with vanilla JupyterLab
2. **True Tab Management**: `?reset` actually closes other tabs
3. **Workspace Isolation**: Each conversation in its own workspace
4. **URL-Based**: Shareable, bookmarkable conversation links
5. **Iframe Compatible**: Works in invisible iframes
6. **HTTP Redirects**: Server can trigger browser navigation
7. **Programmatic Control**: Server-side conversation switching

## 🚧 **Implementation Requirements**

1. **Update MCP Server**: Add URL-based navigation tools
2. **Client WebSocket Handler**: Listen for navigation messages
3. **Workspace Management**: Create/cleanup conversation workspaces
4. **URL Construction**: Build proper JupyterLab URLs with tokens

## 🎯 **Testing Strategy**

1. **Manual URL Testing**: Verify `?reset` parameter behavior
2. **Workspace API Testing**: Test workspace creation/deletion
3. **HTTP Redirect Testing**: Verify server-triggered navigation
4. **Iframe Integration**: Test invisible iframe operation
5. **Conversation Flow**: End-to-end conversation switching

---

**Verdict**: This approach could **solve the core limitation** while keeping MCP server benefits!

**Next Step**: Implement `switch_notebook` tool with URL-based navigation and test the `?reset` behavior. 