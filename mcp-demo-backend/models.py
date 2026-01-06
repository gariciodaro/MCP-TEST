"""
Pydantic models for API request/response schemas.
"""

from typing import Any, Optional
from pydantic import BaseModel


# =============================================================================
# Request Models
# =============================================================================

class ConnectRequest(BaseModel):
    """Request to connect to an MCP server."""
    server_path: str


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    message: str


class ResourceReadRequest(BaseModel):
    """Request to read a resource."""
    uri: str


class PromptGetRequest(BaseModel):
    """Request to get a prompt."""
    name: str
    arguments: dict[str, str] = {}


# =============================================================================
# Response Models
# =============================================================================

class ToolCallResponse(BaseModel):
    """A single tool call in a chat response."""
    name: str
    arguments: dict[str, Any]
    result: str


class ChatResponse(BaseModel):
    """Response from a chat message."""
    response: str
    tool_calls: list[ToolCallResponse]


class ServerStatus(BaseModel):
    """Current server connection status."""
    connected: bool
    server_path: Optional[str] = None
    tools: list[dict] = []
    resources: list[dict] = []
    prompts: list[dict] = []
