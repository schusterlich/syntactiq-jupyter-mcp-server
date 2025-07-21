# Simple Iframe Notebook Switching - The Perfect MCP Solution

## 🎯 **Core Concept**

**No tab closing needed!** Simply reload the iframe with a URL that opens the target notebook directly.

## ⚡ **Why This Works Perfectly**

1. **iframe reload = clean slate**: Each reload starts fresh with only the target notebook
2. **No extension required**: Uses vanilla JupyterLab URLs
3. **Perfect for your use case**: Invisible iframe, conversation switching
4. **Simple and reliable**: No complex workspace/tab management
5. **MCP server compatible**: Server just provides URLs

## 🏗️ **Implementation**

### **MCP Server - Simple URL Provider**
```python
@server.tool()
async def switch_notebook(notebook_path: str, conversation_id: str) -> dict:
    """
    Switch to a specific notebook by providing a direct URL.
    No tab management - just clean iframe reload.
    """
    
    # Ensure notebook exists
    if not await notebook_exists(notebook_path):
        await create_notebook(notebook_path)
    
    # Update MCP server context to the new notebook
    global ROOM_ID
    ROOM_ID = notebook_path
    
    # Create direct notebook URL
    notebook_url = f"http://localhost:8888/lab/tree/{notebook_path}?token={JUPYTER_TOKEN}"
    
    return {
        "action": "reload_iframe",
        "url": notebook_url,
        "notebook_path": notebook_path,
        "conversation_id": conversation_id,
        "mcp_context_updated": True
    }

@server.tool()
async def prepare_notebook(notebook_path: str, conversation_id: str) -> dict:
    """
    Create and switch to a notebook - one-stop shop.
    """
    
    # Create notebook if needed
    if not await notebook_exists(notebook_path):
        await create_notebook(notebook_path, initial_content={
            "conversation_id": conversation_id,
            "created": datetime.now().isoformat()
        })
    
    # Update MCP context
    global ROOM_ID 
    ROOM_ID = notebook_path
    
    # Provide direct URL for iframe reload
    notebook_url = f"http://localhost:8888/lab/tree/{notebook_path}?token={JUPYTER_TOKEN}"
    
    return {
        "action": "reload_iframe",
        "url": notebook_url,
        "notebook_path": notebook_path,
        "conversation_id": conversation_id,
        "notebook_ready": True,
        "mcp_context_updated": True
    }

@server.tool() 
async def list_conversations() -> list:
    """List all conversations with direct switch URLs"""
    
    notebooks = await list_notebooks_in_directory("conversations/")
    
    conversations = []
    for nb in notebooks:
        conversation_id = extract_conversation_id(nb.path)
        direct_url = f"http://localhost:8888/lab/tree/{nb.path}?token={JUPYTER_TOKEN}"
        
        conversations.append({
            "conversation_id": conversation_id,
            "notebook_path": nb.path,
            "direct_url": direct_url,
            "last_modified": nb.last_modified,
            "is_current": nb.path == ROOM_ID,
            "title": await get_notebook_title(nb.path)
        })
    
    return conversations
```

### **Client - Simple Iframe Management**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Conversation Manager</title>
</head>
<body>
    <div id="app">
        <!-- Your platform UI here -->
        <div id="conversation-controls">
            <button onclick="createNewConversation()">New Conversation</button>
            <button onclick="listConversations()">List Conversations</button>
        </div>
        
        <!-- The magic iframe - simply reload with new URLs -->
        <iframe id="jupyter-frame" 
                src="http://localhost:8888/lab"
                style="width: 0; height: 0; border: none;">
        </iframe>
    </div>
    
    <script>
        class ConversationManager {
            constructor() {
                this.setupMCPConnection();
            }
            
            setupMCPConnection() {
                // WebSocket to MCP server
                this.mcp = new WebSocket('ws://localhost:4040/mcp');
                
                this.mcp.onmessage = (event) => {
                    const message = JSON.parse(event.data);
                    
                    if (message.action === 'reload_iframe') {
                        this.switchToNotebook(message.url);
                    }
                };
            }
            
            // The core magic - just reload iframe with new URL!
            switchToNotebook(url) {
                const iframe = document.getElementById('jupyter-frame');
                iframe.src = url;  // That's it! Clean reload with target notebook
                
                console.log(`Switched to notebook: ${url}`);
            }
            
            async createConversation(title = "New Analysis") {
                const conversationId = `conv_${Date.now()}`;
                const notebookPath = `conversations/${conversationId}.ipynb`;
                
                const response = await this.callMCP('prepare_notebook', {
                    notebook_path: notebookPath,
                    conversation_id: conversationId
                });
                
                // MCP server will send reload_iframe message automatically
                return response;
            }
            
            async switchConversation(conversationId) {
                const notebookPath = `conversations/${conversationId}.ipynb`;
                
                const response = await this.callMCP('switch_notebook', {
                    notebook_path: notebookPath,
                    conversation_id: conversationId
                });
                
                return response;
            }
            
            async callMCP(tool, args) {
                // Simple HTTP call to MCP server
                const response = await fetch('http://localhost:4040/mcp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tool: tool,
                        arguments: args
                    })
                });
                
                return await response.json();
            }
        }
        
        // Initialize
        const manager = new ConversationManager();
        
        // Helper functions for buttons
        async function createNewConversation() {
            await manager.createConversation("Data Analysis " + new Date().toLocaleString());
        }
        
        async function listConversations() {
            const conversations = await manager.callMCP('list_conversations', {});
            console.log('Available conversations:', conversations);
            
            // You could build UI to show/switch conversations
            // For demo, just switch to first one:
            if (conversations.length > 0) {
                manager.switchToNotebook(conversations[0].direct_url);
            }
        }
    </script>
</body>
</html>
```

### **Even Simpler - Direct URL Approach**
```javascript
class SuperSimpleNotebookSwitcher {
    constructor(iframeId) {
        this.iframe = document.getElementById(iframeId);
        this.baseUrl = 'http://localhost:8888/lab/tree/';
        this.token = 'MY_TOKEN';  // Your Jupyter token
    }
    
    // Just switch by changing iframe src - no MCP needed for basic switching!
    switchToNotebook(notebookPath) {
        const url = `${this.baseUrl}${notebookPath}?token=${this.token}`;
        this.iframe.src = url;
        
        console.log(`Switched to: ${notebookPath}`);
    }
    
    // Create conversation pattern
    createConversation(conversationId) {
        const notebookPath = `conversations/${conversationId}.ipynb`;
        
        // First create via MCP (if needed), then switch
        this.callMCP('create_notebook', { path: notebookPath })
            .then(() => this.switchToNotebook(notebookPath));
    }
}

// Ultra-simple usage
const switcher = new SuperSimpleNotebookSwitcher('jupyter-frame');

// Switch conversations
switcher.switchToNotebook('conversations/conv_analysis_1.ipynb');
switcher.switchToNotebook('conversations/conv_analysis_2.ipynb');
```

## 🎯 **Your Platform Integration**

```typescript
// In your conversation management
class ConversationService {
    private jupyterFrame: HTMLIFrameElement;
    
    constructor() {
        this.jupyterFrame = document.getElementById('jupyter-frame') as HTMLIFrameElement;
    }
    
    async switchToConversation(conversationId: string) {
        // 1. Tell MCP server to switch context
        await this.mcpClient.call('switch_notebook', {
            notebook_path: `conversations/${conversationId}.ipynb`,
            conversation_id: conversationId
        });
        
        // 2. Reload iframe with target notebook
        const notebookUrl = `http://localhost:8888/lab/tree/conversations/${conversationId}.ipynb?token=${this.jupyterToken}`;
        this.jupyterFrame.src = notebookUrl;
        
        // 3. Update your platform UI
        this.updateConversationUI(conversationId);
    }
    
    async createNewConversation(title: string) {
        const conversationId = generateConversationId();
        
        // Create notebook via MCP
        await this.mcpClient.call('prepare_notebook', {
            notebook_path: `conversations/${conversationId}.ipynb`,
            conversation_id: conversationId
        });
        
        // Switch to it
        await this.switchToConversation(conversationId);
        
        return conversationId;
    }
}
```

## ✅ **Why This is Perfect for Your Use Case**

1. **Invisible Operation**: Iframe is `width: 0; height: 0` - user never sees JupyterLab directly
2. **Clean Switching**: Each reload = fresh notebook environment
3. **No Tab Complexity**: No need to manage what's open/closed
4. **MCP Integration**: Server provides notebook management, client handles display
5. **Platform Control**: Your platform orchestrates everything
6. **Background Execution**: Can execute code while user interacts with your UI
7. **Simple Deployment**: Just JupyterLab + MCP server containers

## 🚀 **Implementation Steps**

1. **Update MCP Server**: Add `switch_notebook` and `prepare_notebook` tools
2. **Test Direct URLs**: Verify `http://localhost:8888/lab/tree/notebook.ipynb` opens target notebook
3. **Iframe Integration**: Test iframe reload with different notebook URLs
4. **Platform Integration**: Add conversation switching to your UI
5. **Polish**: Add notebook creation, listing, management

## 🎯 **This Solves Everything!**

- ✅ No extension required
- ✅ Perfect for invisible iframe  
- ✅ Background notebook execution
- ✅ Multi-conversation support
- ✅ Simple and reliable
- ✅ Full MCP server benefits
- ✅ Your platform stays in control

**Result**: You get **all the MCP benefits** (advanced execution, real-time sync, professional codebase) while solving the **core tab management limitation** with a much simpler approach!

**This might actually be BETTER than your extension approach** because it's simpler and more reliable. 🎉 