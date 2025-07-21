import json
import time
from jupyter_server.base.handlers import JupyterHandler
from jupyter_server.extension.handler import ExtensionHandlerMixin
from tornado.websocket import WebSocketHandler

# --- Globals for Routing ---
# All connected clients
_ws_clients = set()
# Clients that have identified as a JupyterLab frontend via heartbeat
_frontend_clients = set()
# Maps a unique request key to the tool client that initiated it
_active_requests = {}
# Timestamp of the last heartbeat received from a frontend
_last_frontend_heartbeat = 0


class HotReloadWebSocketHandler(WebSocketHandler, JupyterHandler, ExtensionHandlerMixin):
    """WebSocket handler with robust routing for notebook interactions."""

    def open(self):
        """Handle new WebSocket connections."""
        _ws_clients.add(self)
        self.log.info(f"WebSocket opened. Total clients: {len(_ws_clients)}")

    def on_close(self):
        """Handle WebSocket connection close and clean up."""
        _ws_clients.discard(self)
        _frontend_clients.discard(self)

        # Clean up any active requests from the disconnected client
        keys_to_remove = [key for key, client in _active_requests.items() if client == self]
        for key in keys_to_remove:
            del _active_requests[key]
        
        self.log.info(f"WebSocket closed. Remaining clients: {len(_ws_clients)}")

    def get_request_key(self, data: dict) -> str | None:
        """Generates a consistent, unique key for a request."""
        action = data.get("action")
        path = data.get("path")
        cell_id = data.get("cell_id")

        if not path:
            return None

        # Cell-specific actions are keyed by action, path, and cell_id
        if action in ["execute-cell", "replace-cell", "delete-cell"]:
            return f"{action}:{path}:{cell_id}"
        
        # Other actions are keyed by action and path. This assumes only one such operation
        # is active per path at a time (e.g., one 'insert-cell' for a given notebook).
        elif action in ["open-notebook", "save", "get-cells", "insert-cell", "close-notebook-tab"]:
            return f"{action}:{path}"
        
        return None

    def on_message(self, message: str):
        """Handle incoming WebSocket messages and route them appropriately."""
        global _last_frontend_heartbeat
        try:
            data = json.loads(message)
            action = data.get("action")

            if action == "frontend-heartbeat":
                _last_frontend_heartbeat = time.time()
                if self not in _frontend_clients:
                    _frontend_clients.add(self)
                    self.log.info("Client identified as a frontend.")
                return

            if action == "get-client-count":
                self.write_message(json.dumps({
                    "action": "client-count",
                    "count": len(_ws_clients),
                    "frontend_count": len(_frontend_clients),
                    "last_frontend_heartbeat": _last_frontend_heartbeat
                }))
                return

            # Requests from tools should be routed to the frontend
            if self not in _frontend_clients:
                self.route_request_to_frontend(data, message)
            # Responses from the frontend should be routed back to the tool
            else:
                self.route_response_to_tool(data, message)

        except Exception as e:
            self.log.error(f"Error processing message: {e}", exc_info=True)

    def route_request_to_frontend(self, data: dict, original_message: str):
        """Routes a request from a tool client to all connected frontends."""
        request_key = self.get_request_key(data)
        if not request_key:
            self.log.warning(f"Ignoring unroutable request from tool: {data.get('action')}")
            return
            
        if not _frontend_clients:
            self.log.warning("Request received, but no frontend is connected to forward it to.")
            # Optionally notify the tool that the command failed
            error_response = json.dumps({
                "action": f"{data.get('action')}-failed", 
                "error": "No frontend connected.",
                "path": data.get("path"),
                "cell_id": data.get("cell_id")
            })
            self.write_message(error_response)
            return

        _active_requests[request_key] = self  # `self` is the tool client
        self.log.info(f"Routing request with key '{request_key}' to {len(_frontend_clients)} frontend(s).")
        
        for client in _frontend_clients:
            client.write_message(original_message)

    def route_response_to_tool(self, data: dict, original_message: str):
        """Finds the original tool for a response from a frontend and forwards it."""
        response_action = data.get("action")
        path = data.get("path")

        # Map frontend response actions back to the original tool request actions
        action_map = {
            "notebook-opened": "open-notebook", "saved": "save", "cells-data": "get-cells",
            "cell-inserted": "insert-cell", "cell-executed": "execute-cell",
            "cell-replaced": "replace-cell", "cell-deleted": "delete-cell",
            "notebook-tab-closed": "close-notebook-tab",
            "cell-execution-acknowledged": "execute-cell"  # Special case: an interim response
        }
        original_action = action_map.get(response_action)

        if not original_action:
            self.log.warning(f"Ignoring response with unhandled action: {response_action}")
            return

        # Reconstruct the key from the response data
        if original_action in ["execute-cell", "replace-cell", "delete-cell"]:
            request_key = f"{original_action}:{path}:{data.get('cell_id')}"
        else:
            request_key = f"{original_action}:{path}"
        
        requester = _active_requests.get(request_key)
        if not requester:
            # It's normal to not find a key for acknowledgements, as the final response will clean it up.
            if response_action != "cell-execution-acknowledged":
                self.log.warning(f"No active request found for response key '{request_key}'.")
            return
            
        if requester in _ws_clients:
            self.log.info(f"Forwarding response for key '{request_key}' to original tool.")
            requester.write_message(original_message)
        else:
            self.log.warning(f"Original requester for key '{request_key}' is no longer connected.")
        
        # Clean up the request key only on the *final* response, not on interim ones like 'acknowledged'
        is_final_response = response_action not in ["cell-execution-acknowledged"]
        if is_final_response and request_key in _active_requests:
            del _active_requests[request_key]

def setup_handlers(web_app):
    """Setup the WebSocket handler for JupyterLab."""
    host_pattern = ".*$"
    base_url = web_app.settings["base_url"]
    route_pattern = f"{base_url}api/hotreload/ws"

    handlers = [(route_pattern, HotReloadWebSocketHandler)]

    web_app.add_handlers(host_pattern, handlers)
    print(f"HotReload extension: added handler at {route_pattern}")
