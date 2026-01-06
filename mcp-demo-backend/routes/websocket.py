"""
WebSocket endpoint with elicitation support.

This module handles real-time chat connections that support MCP's
elicitation feature - allowing tools to request user input mid-execution.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

from config import get_api_key
from mcp_client import MCPClient


router = APIRouter()


# =============================================================================
# WebSocket Session
# =============================================================================

class WebSocketSession:
    """
    Manages a single WebSocket connection with its own MCP client.
    
    Each connection gets an independent MCP client instance,
    allowing multiple users to have separate sessions.
    
    The session handles:
    - MCP server connection
    - Chat message processing
    - Elicitation (pausing for user input mid-tool-execution)
    """
    
    def __init__(self, websocket: WebSocket, api_key: str):
        self.websocket = websocket
        self.client = MCPClient(api_key)
    
    async def send(self, data: dict) -> None:
        """Send JSON message to the client."""
        await self.websocket.send_json(data)
    
    async def handle_elicitation(self, message: str, schema: dict) -> dict:
        """
        Handle elicitation request from MCP tool.
        
        When a tool calls ctx.elicit(), this method:
        1. Sends the request to the frontend
        2. Waits for user response (up to 2 minutes)
        3. Returns the response to continue tool execution
        
        This is the "magic" that allows tools to pause and ask questions.
        
        Note: We must receive WebSocket messages HERE because the main
        message loop is blocked waiting for this function to return.
        """
        await self.send({
            "type": "elicitation",
            "message": message,
            "schema": schema
        })
        
        # We need to receive messages directly here because the main
        # handle_messages loop is blocked waiting for process_query to finish
        start_time = asyncio.get_event_loop().time()
        timeout = 120  # 2 minutes
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning("Elicitation timed out waiting for user response")
                return {"action": "cancel", "reason": "timeout"}
            
            try:
                # Wait for next message with remaining timeout
                remaining = timeout - elapsed
                data = await asyncio.wait_for(
                    self.websocket.receive_json(),
                    timeout=min(remaining, 30)  # Check every 30s max
                )
                
                logger.warning(f"Elicitation received message: {data}")
                
                if data.get("type") == "elicitation_response":
                    return {
                        "action": data.get("action", "cancel"),
                        "data": data.get("data", {})
                    }
                # Ignore other message types during elicitation
                
            except asyncio.TimeoutError:
                # Just a periodic check, continue waiting
                continue
    
    async def cleanup(self) -> None:
        """Release all resources."""
        await self.client.cleanup()


# =============================================================================
# Message Handlers
# =============================================================================

async def handle_connect(session: WebSocketSession, data: dict) -> None:
    """Handle 'connect' message - connect to MCP server."""
    server_path = data.get("server_path")
    
    if not server_path:
        await session.send({"type": "error", "message": "server_path required"})
        return
    
    try:
        tools = await session.client.connect(server_path)
        resources = await session.client.list_resources()
        prompts = await session.client.list_prompts()
        
        await session.send({
            "type": "connected",
            "tools": tools,
            "resources": resources,
            "prompts": prompts
        })
    except Exception as e:
        await session.send({"type": "error", "message": str(e)})


async def handle_chat(session: WebSocketSession, data: dict) -> None:
    """Handle 'chat' message - process user query."""
    message = data.get("message", "")
    
    if not message:
        await session.send({"type": "error", "message": "message required"})
        return
    
    if not session.client.connected:
        await session.send({"type": "error", "message": "Not connected to MCP server"})
        return
    
    try:
        result = await session.client.process_query(
            message,
            elicitation_callback=session.handle_elicitation
        )
        
        await session.send({
            "type": "response",
            "content": result.content,
            "tool_calls": [
                {
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "result": tc.result
                }
                for tc in result.tool_calls
            ]
        })
    except Exception as e:
        await session.send({"type": "error", "message": str(e)})


async def handle_read_resource(session: WebSocketSession, data: dict) -> None:
    """Handle 'read_resource' message - read a resource by URI."""
    uri = data.get("uri")
    
    if not uri:
        await session.send({"type": "error", "message": "uri required"})
        return
    
    if not session.client.connected:
        await session.send({"type": "error", "message": "Not connected to MCP server"})
        return
    
    try:
        result = await session.client.read_resource(uri)
        await session.send({
            "type": "resource_content",
            "uri": uri,
            "content": result.get("content", ""),
            "error": result.get("error")
        })
    except Exception as e:
        await session.send({"type": "error", "message": str(e)})


async def handle_get_prompt(session: WebSocketSession, data: dict) -> None:
    """Handle 'get_prompt' message - get a prompt with arguments."""
    name = data.get("name")
    arguments = data.get("arguments", {})
    
    if not name:
        await session.send({"type": "error", "message": "name required"})
        return
    
    if not session.client.connected:
        await session.send({"type": "error", "message": "Not connected to MCP server"})
        return
    
    try:
        result = await session.client.get_prompt(name, arguments)
        await session.send({
            "type": "prompt_content",
            "name": name,
            "messages": result.get("messages", []),
            "error": result.get("error")
        })
    except Exception as e:
        await session.send({"type": "error", "message": str(e)})


async def handle_messages(session: WebSocketSession) -> None:
    """
    Main message loop for a WebSocket connection.
    
    Routes incoming messages to appropriate handlers based on 'type' field.
    Note: elicitation_response is handled directly in handle_elicitation.
    """
    while True:
        data = await session.websocket.receive_json()
        msg_type = data.get("type")
        
        if msg_type == "connect":
            await handle_connect(session, data)
        
        elif msg_type == "chat":
            await handle_chat(session, data)
        
        elif msg_type == "read_resource":
            await handle_read_resource(session, data)
        
        elif msg_type == "get_prompt":
            await handle_get_prompt(session, data)
        
        elif msg_type == "disconnect":
            break


# =============================================================================
# WebSocket Endpoint
# =============================================================================

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for chat with elicitation support.
    
    Protocol:
    
    Client -> Server:
        {"type": "connect", "server_path": "path/to/server.py"}
        {"type": "chat", "message": "Hello"}
        {"type": "elicitation_response", "action": "accept", "data": {...}}
        {"type": "disconnect"}
    
    Server -> Client:
        {"type": "connected", "tools": [...], "resources": [...], "prompts": [...]}
        {"type": "elicitation", "message": "...", "schema": {...}}
        {"type": "response", "content": "...", "tool_calls": [...]}
        {"type": "error", "message": "..."}
    """
    await websocket.accept()
    
    # Validate API key
    try:
        api_key = get_api_key()
    except ValueError as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()
        return
    
    # Create session and handle messages
    session = WebSocketSession(websocket, api_key)
    
    try:
        await handle_messages(session)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await session.send({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        await session.cleanup()
