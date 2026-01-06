"""
HTTP REST API endpoints.

These endpoints provide basic MCP operations without elicitation support.
Useful for testing, scripts, and simple integrations.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException

from config import get_api_key
from mcp_client import MCPClient, ToolCall
from models import (
    ConnectRequest,
    ChatRequest,
    ChatResponse,
    ResourceReadRequest,
    PromptGetRequest,
    ServerStatus,
    ToolCallResponse,
)


router = APIRouter()

# Global MCP client for HTTP endpoints (shared across requests)
http_client: Optional[MCPClient] = None


# =============================================================================
# Lifecycle Management
# =============================================================================

async def startup() -> None:
    """Initialize HTTP client on startup."""
    global http_client
    try:
        http_client = MCPClient(get_api_key())
    except ValueError as e:
        print(f"WARNING: {e}")


async def shutdown() -> None:
    """Cleanup HTTP client on shutdown."""
    if http_client:
        await http_client.cleanup()


# =============================================================================
# Helper Functions
# =============================================================================

def require_client() -> MCPClient:
    """Get the HTTP client, raising an error if not available."""
    if not http_client:
        raise HTTPException(status_code=500, detail="API key not configured")
    return http_client


def require_connection() -> MCPClient:
    """Get the HTTP client and verify it's connected."""
    client = require_client()
    if not client.connected:
        raise HTTPException(status_code=400, detail="Not connected to MCP server")
    return client


def format_tool_calls(tool_calls: list[ToolCall]) -> list[ToolCallResponse]:
    """Convert internal ToolCall objects to API response format."""
    return [
        ToolCallResponse(
            name=tc.name,
            arguments=tc.arguments,
            result=tc.result
        )
        for tc in tool_calls
    ]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "MCP Demo API", "status": "running"}


@router.get("/status", response_model=ServerStatus)
async def get_status():
    """Get current MCP server connection status."""
    if not http_client or not http_client.connected:
        return ServerStatus(connected=False)
    
    return ServerStatus(
        connected=True,
        server_path=http_client.server_path,
        tools=await http_client.list_tools(),
        resources=await http_client.list_resources(),
        prompts=await http_client.list_prompts()
    )


@router.post("/connect")
async def connect_to_server(request: ConnectRequest):
    """Connect to an MCP server."""
    global http_client
    client = require_client()
    
    # Reconnect if already connected
    if client.connected:
        await client.cleanup()
        http_client = MCPClient(get_api_key())
        client = http_client
    
    try:
        tools = await client.connect(request.server_path)
        resources = await client.list_resources()
        prompts = await client.list_prompts()
        
        return {
            "status": "connected",
            "server_path": request.server_path,
            "tools": tools,
            "resources": resources,
            "prompts": prompts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disconnect")
async def disconnect_from_server():
    """Disconnect from the MCP server."""
    global http_client
    
    if http_client and http_client.connected:
        await http_client.cleanup()
        http_client = MCPClient(get_api_key())
        return {"status": "disconnected"}
    
    return {"status": "not_connected"}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message and get a response using MCP tools."""
    client = require_connection()
    
    try:
        result = await client.process_query(request.message)
        return ChatResponse(
            response=result.content,
            tool_calls=format_tool_calls(result.tool_calls)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def get_tools():
    """Get list of available tools."""
    client = require_connection()
    return {"tools": await client.list_tools()}


@router.get("/resources")
async def get_resources():
    """Get list of available resources."""
    client = require_connection()
    return {"resources": await client.list_resources()}


@router.post("/resources/read")
async def read_resource(request: ResourceReadRequest):
    """Read a specific resource."""
    client = require_connection()
    result = await client.read_resource(request.uri)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/prompts")
async def get_prompts():
    """Get list of available prompts."""
    client = require_connection()
    return {"prompts": await client.list_prompts()}


@router.post("/prompts/get")
async def get_prompt(request: PromptGetRequest):
    """Get a specific prompt with arguments filled in."""
    client = require_connection()
    result = await client.get_prompt(request.name, request.arguments)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
