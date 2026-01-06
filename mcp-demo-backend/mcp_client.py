"""
MCP Client - Unified client for Model Context Protocol servers.

This module provides a single, clean interface for:
- Connecting to MCP servers via stdio
- Listing and calling tools, resources, and prompts
- Processing queries with Claude (with optional elicitation support)

Design Principles:
- Single Responsibility: One class, one purpose
- DRY: No duplicate code paths
- Explicit > Implicit: Clear method signatures and return types
"""

import asyncio
import json
import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from anthropic import Anthropic

logger = logging.getLogger(__name__)
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    TextContent,
    SamplingMessage,
    SamplingCapability,
)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ToolCall:
    """Record of a tool invocation during query processing."""
    name: str
    arguments: dict[str, Any]
    result: str


@dataclass
class SamplingRequest:
    """Represents a sampling request from an MCP server."""
    messages: list[dict]
    system_prompt: Optional[str]
    max_tokens: int


@dataclass
class MCPResponse:
    """Response from processing a user query."""
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


# =============================================================================
# Type Aliases
# =============================================================================

# Callback signature for elicitation: (message, schema) -> user response
ElicitationCallback = Callable[[str, dict], Awaitable[dict[str, Any]]]

# Callback signature for sampling: (request) -> approved response or None
# Returns tuple of (approved: bool, response: str | None)
SamplingCallback = Callable[[SamplingRequest], Awaitable[tuple[bool, Optional[str]]]]


# =============================================================================
# Elicitation Support (Optional FastMCP Integration)
# =============================================================================

try:
    from fastmcp import Client as FastMCPClient
    from fastmcp.client.elicitation import ElicitResult
    ELICITATION_AVAILABLE = True
except ImportError:
    ELICITATION_AVAILABLE = False
    FastMCPClient = None
    ElicitResult = None


def build_schema_from_dataclass(dataclass_type) -> dict:
    """
    Build a JSON schema from a dataclass type.
    
    This allows the frontend to render a dynamic form based on
    the fields the MCP server is requesting.
    """
    schema = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    type_mapping = {
        int: "integer",
        float: "number",
        bool: "boolean",
        str: "string",
    }
    
    for name, field_info in dataclass_type.__dataclass_fields__.items():
        field_type = field_info.type
        json_type = type_mapping.get(field_type, "string")
        
        schema["properties"][name] = {
            "type": json_type,
            "title": name.replace("_", " ").title()
        }
        schema["required"].append(name)
    
    return schema


# =============================================================================
# Main Client Class
# =============================================================================

class MCPClient:
    """
    Unified MCP Client with optional elicitation and sampling support.
    
    Usage:
        client = MCPClient(api_key)
        await client.connect("path/to/server.py")
        
        # Simple query (no elicitation)
        response = await client.process_query("What's the weather?")
        
        # Query with elicitation support
        response = await client.process_query(
            "Plan a trip",
            elicitation_callback=my_callback
        )
        
        await client.cleanup()
    
    Sampling:
        The MCP server can request the client to make LLM calls.
        Set a sampling_callback to approve/handle these requests.
    """
    
    def __init__(self, api_key: str, sampling_callback: Optional[SamplingCallback] = None):
        """
        Initialize the MCP client.
        
        Args:
            api_key: Anthropic API key for Claude interactions
            sampling_callback: Optional callback for server-initiated LLM requests.
                              Called with SamplingRequest, returns (approved, response).
        """
        self.api_key = api_key
        self.anthropic = Anthropic(api_key=api_key)
        self.exit_stack = AsyncExitStack()
        self.sampling_callback = sampling_callback
        
        # Connection state
        self.session: Optional[ClientSession] = None
        self.server_path: str = ""
        self.connected: bool = False
    
    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------
    
    async def connect(self, server_path: str) -> list[dict]:
        """
        Connect to an MCP server.
        
        Args:
            server_path: Path to the server script (.py or .js)
            
        Returns:
            List of available tools
            
        Raises:
            ValueError: If server_path is not a .py or .js file
        """
        if not server_path.endswith(('.py', '.js')):
            raise ValueError("Server script must be a .py or .js file")
        
        command = "python" if server_path.endswith('.py') else "node"
        
        server_params = StdioServerParameters(
            command=command,
            args=[server_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport
        
        # Build sampling callback wrapper if provided
        sampling_fn = None
        sampling_caps = None
        if self.sampling_callback:
            sampling_fn = self._create_sampling_handler()
            # Advertise sampling capability to the server
            sampling_caps = SamplingCapability()
            logger.info(f"Sampling callback configured: {sampling_fn}, capabilities: {sampling_caps}")
        else:
            logger.warning("No sampling callback provided!")
        
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(
                read_stream, 
                write_stream, 
                sampling_callback=sampling_fn,
                sampling_capabilities=sampling_caps
            )
        )
        
        # Debug: verify the session's sampling callback
        logger.info(f"Session sampling callback: {self.session._sampling_callback}")
        
        await self.session.initialize()
        self.server_path = server_path
        self.connected = True
        
        return await self.list_tools()
    
    def _create_sampling_handler(self):
        """
        Create a sampling handler function for the ClientSession.
        
        This wraps our callback and handles the MCP protocol conversion.
        The MCP server calls create_message() and we respond with LLM output.
        """
        async def sampling_handler(context, params: CreateMessageRequestParams):
            """Handle sampling request from MCP server."""
            logger.info(f"Sampling request received: {len(params.messages)} messages, max_tokens={params.maxTokens}")
            
            # Convert MCP messages to our format
            messages = []
            for msg in params.messages:
                content = msg.content
                if hasattr(content, 'text'):
                    content = content.text
                messages.append({
                    "role": msg.role,
                    "content": str(content)
                })
            
            # Create the sampling request
            request = SamplingRequest(
                messages=messages,
                system_prompt=params.systemPrompt,
                max_tokens=params.maxTokens
            )
            
            # Call user's callback for approval
            try:
                approved, response_text = await self.sampling_callback(request)
                
                if not approved:
                    # User rejected the sampling request
                    logger.info("Sampling request rejected by user")
                    return CreateMessageResult(
                        role="assistant",
                        content=TextContent(type="text", text="[Sampling request rejected by user]"),
                        model="rejected",
                        stopReason="endTurn"
                    )
                
                # If callback provided a response, use it directly
                if response_text:
                    logger.info(f"Sampling callback provided response: {response_text[:100]}...")
                    return CreateMessageResult(
                        role="assistant",
                        content=TextContent(type="text", text=response_text),
                        model="user-provided",
                        stopReason="endTurn"
                    )
                
                # Otherwise, make the LLM call ourselves
                logger.info("Making LLM call for approved sampling request")
                
                # Build messages for Claude
                claude_messages = messages
                
                # Make the API call
                api_response = self.anthropic.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=params.maxTokens,
                    system=params.systemPrompt or "",
                    messages=claude_messages
                )
                
                # Extract text from response
                result_text = ""
                for block in api_response.content:
                    if block.type == 'text':
                        result_text += block.text
                
                logger.info(f"LLM sampling response: {result_text[:100]}...")
                
                return CreateMessageResult(
                    role="assistant",
                    content=TextContent(type="text", text=result_text),
                    model=api_response.model,
                    stopReason=api_response.stop_reason or "endTurn"
                )
                
            except Exception as e:
                logger.error(f"Sampling error: {e}")
                return CreateMessageResult(
                    role="assistant",
                    content=TextContent(type="text", text=f"[Sampling error: {e}]"),
                    model="error",
                    stopReason="endTurn"
                )
        
        return sampling_handler
    
    async def cleanup(self) -> None:
        """Disconnect and release all resources."""
        self.connected = False
        self.session = None
        self.server_path = ""
        await self.exit_stack.aclose()
        self.exit_stack = AsyncExitStack()
    
    # -------------------------------------------------------------------------
    # MCP Primitives: Tools, Resources, Prompts
    # -------------------------------------------------------------------------
    
    async def list_tools(self) -> list[dict]:
        """Get available tools from the MCP server."""
        if not self.session:
            return []
        
        response = await self.session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
            for tool in response.tools
        ]
    
    async def list_resources(self) -> list[dict]:
        """Get available resources from the MCP server."""
        if not self.session:
            return []
        
        try:
            response = await self.session.list_resources()
            return [
                {
                    "uri": str(res.uri),
                    "name": res.name,
                    "description": getattr(res, 'description', ''),
                    "mimeType": getattr(res, 'mimeType', 'text/plain')
                }
                for res in response.resources
            ]
        except Exception:
            return []
    
    async def list_prompts(self) -> list[dict]:
        """Get available prompts from the MCP server."""
        if not self.session:
            return []
        
        try:
            response = await self.session.list_prompts()
            return [
                {
                    "name": prompt.name,
                    "description": getattr(prompt, 'description', ''),
                    "arguments": [
                        {
                            "name": arg.name,
                            "description": getattr(arg, 'description', ''),
                            "required": getattr(arg, 'required', False)
                        }
                        for arg in getattr(prompt, 'arguments', []) or []
                    ]
                }
                for prompt in response.prompts
            ]
        except Exception:
            return []
    
    async def read_resource(self, uri: str) -> dict:
        """
        Read content from a resource.
        
        Args:
            uri: Resource URI to read
            
        Returns:
            Dict with 'uri' and 'content', or 'error' on failure
        """
        if not self.session:
            return {"error": "Not connected"}
        
        try:
            response = await self.session.read_resource(uri)
            content = response.contents[0].text if response.contents else ""
            return {"uri": uri, "content": content}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_prompt(
        self, 
        name: str, 
        arguments: Optional[dict[str, str]] = None
    ) -> dict:
        """
        Get a prompt with arguments filled in.
        
        Args:
            name: Prompt name
            arguments: Optional dict of argument values
            
        Returns:
            Dict with 'name', 'description', 'messages', or 'error'
        """
        if not self.session:
            return {"error": "Not connected"}
        
        try:
            response = await self.session.get_prompt(name, arguments=arguments or {})
            messages = []
            
            for msg in response.messages:
                content = msg.content
                
                # Handle different content types
                if hasattr(content, 'text'):
                    content = content.text
                elif isinstance(content, list):
                    content = ' '.join(
                        c.text if hasattr(c, 'text') else str(c)
                        for c in content
                    )
                
                messages.append({
                    "role": msg.role,
                    "content": str(content)
                })
            
            return {
                "name": name,
                "description": getattr(response, 'description', ''),
                "messages": messages
            }
        except Exception as e:
            return {"error": str(e)}
    
    # -------------------------------------------------------------------------
    # Tool Execution
    # -------------------------------------------------------------------------
    
    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        elicitation_callback: Optional[ElicitationCallback] = None
    ) -> str:
        """
        Call a tool, optionally with elicitation support.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            elicitation_callback: Optional callback for user input requests
            
        Returns:
            Tool result as string
        """
        if not self.session:
            return "Error: Not connected"
        
        # Use FastMCP client if elicitation is needed and available
        if elicitation_callback and ELICITATION_AVAILABLE:
            return await self._call_tool_with_elicitation(
                name, arguments, elicitation_callback
            )
        
        # Direct call (no elicitation)
        result = await self.session.call_tool(name, arguments)
        return result.content[0].text if result.content else ""
    
    async def _call_tool_with_elicitation(
        self,
        name: str,
        arguments: dict[str, Any],
        callback: ElicitationCallback
    ) -> str:
        """
        Call a tool using FastMCP client with elicitation handler.
        
        This creates a temporary FastMCP client instance to handle
        the elicitation protocol, then returns the result.
        """
        async def elicitation_handler(message, response_type, params, ctx):
            """Bridge between FastMCP elicitation and our callback."""
            
            # Build schema from the response type
            schema = {}
            if response_type is not None:
                if hasattr(response_type, 'model_json_schema'):
                    schema = response_type.model_json_schema()
                elif hasattr(response_type, '__dataclass_fields__'):
                    schema = build_schema_from_dataclass(response_type)
            
            try:
                response = await asyncio.wait_for(
                    callback(message, schema),
                    timeout=120
                )
                
                action = response.get("action", "cancel")
                data = response.get("data", {})
                
                logger.warning(f"DEBUG elicitation_handler: action={action}, data={data}")
                
                if action == "accept":
                    # MCP protocol expects content as a dict of primitives
                    result = ElicitResult(action="accept", content=data)
                    logger.warning(f"DEBUG returning ElicitResult: {result}")
                    return result
                elif action == "decline":
                    return ElicitResult(action="decline")
                else:
                    return ElicitResult(action="cancel")
                    
            except asyncio.TimeoutError:
                logger.warning("DEBUG elicitation_handler: timeout")
                return ElicitResult(action="cancel")
            except Exception as e:
                logger.warning(f"DEBUG elicitation_handler exception: {e}")
                return ElicitResult(action="cancel")
        
        async def sampling_handler(messages, params, ctx):
            """Bridge between FastMCP sampling and our callback."""
            logger.info(f"FastMCP sampling handler called: {len(messages)} messages")
            
            # Convert MCP messages to our format
            converted_messages = []
            for msg in messages:
                content = msg.content
                if hasattr(content, 'text'):
                    content = content.text
                converted_messages.append({
                    "role": msg.role,
                    "content": str(content)
                })
            
            # Create the sampling request
            request = SamplingRequest(
                messages=converted_messages,
                system_prompt=params.systemPrompt,
                max_tokens=params.maxTokens
            )
            
            # Call user's callback for approval
            if self.sampling_callback:
                approved, response_text = await self.sampling_callback(request)
                
                if not approved:
                    logger.info("Sampling request rejected by user")
                    return "[Sampling request rejected by user]"
                
                if response_text:
                    logger.info(f"User provided response: {response_text[:100]}...")
                    return response_text
                
                # Make the LLM call ourselves
                logger.info("Making LLM call for approved sampling request")
                api_response = self.anthropic.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=params.maxTokens,
                    system=params.systemPrompt or "",
                    messages=converted_messages
                )
                
                result_text = ""
                for block in api_response.content:
                    if block.type == 'text':
                        result_text += block.text
                
                logger.info(f"LLM response: {result_text[:100]}...")
                return result_text
            else:
                return "[No sampling callback configured]"
        
        async with FastMCPClient(
            self.server_path,
            elicitation_handler=elicitation_handler,
            sampling_handler=sampling_handler,
            sampling_capabilities=SamplingCapability()
        ) as client:
            result = await client.call_tool(name, arguments)
            
            # Handle various result types - ensure we return a string
            if hasattr(result, 'data'):
                data = result.data
                if isinstance(data, str):
                    return data
                elif hasattr(data, 'model_dump_json'):
                    # Pydantic model
                    return data.model_dump_json()
                elif hasattr(data, '__dict__'):
                    # Dataclass or regular object
                    return json.dumps(data.__dict__, default=str)
                else:
                    return str(data)
            return str(result)
    
    # -------------------------------------------------------------------------
    # Query Processing (Claude + Tools)
    # -------------------------------------------------------------------------
    
    async def process_query(
        self,
        query: str,
        elicitation_callback: Optional[ElicitationCallback] = None
    ) -> MCPResponse:
        """
        Process a user query using Claude with MCP tools.
        
        This method:
        1. Sends the query to Claude with available tools
        2. Executes any tool calls Claude requests
        3. Continues until Claude provides a final response
        
        Args:
            query: User's question or request
            elicitation_callback: Optional callback for tools that need user input
            
        Returns:
            MCPResponse with content and tool call history
        """
        if not self.session:
            return MCPResponse(content="Not connected to MCP server")
        
        messages = [{"role": "user", "content": query}]
        tools = await self.list_tools()
        tool_calls: list[ToolCall] = []
        final_text: list[str] = []
        
        # Initial Claude request
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=messages,
            tools=tools
        )
        
        # Process tool calls until Claude is done
        while response.stop_reason == "tool_use":
            assistant_content = []
            tool_results = []
            
            for block in response.content:
                assistant_content.append(block)
                
                if block.type == 'text':
                    final_text.append(block.text)
                    
                elif block.type == 'tool_use':
                    # Execute the tool
                    result_text = await self.call_tool(
                        block.name,
                        block.input,
                        elicitation_callback
                    )
                    
                    # Record for response
                    tool_calls.append(ToolCall(
                        name=block.name,
                        arguments=block.input,
                        result=result_text
                    ))
                    
                    # Prepare for Claude
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text
                    })
            
            # Add to conversation
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
            
            # Get next response
            response = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=messages,
                tools=tools
            )
        
        # Extract final text
        for block in response.content:
            if block.type == 'text':
                final_text.append(block.text)
        
        return MCPResponse(
            content="\n".join(final_text),
            tool_calls=tool_calls
        )
