import asyncio
from typing import Optional, List, Dict, Any
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from anthropic import Anthropic


@dataclass
class ToolCall:
    """Represents a tool call made during processing"""
    name: str
    arguments: Dict[str, Any]
    result: Any


@dataclass
class MCPMessage:
    """Represents a message in the conversation"""
    role: str
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)


class MCPClient:
    def __init__(self, anthropic_api_key: str):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic(api_key=anthropic_api_key)
        self.connected = False
        self.server_name = ""
        self.available_tools: List[Dict] = []

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server"""
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()
        self.connected = True
        
        # Get server info
        response = await self.session.list_tools()
        self.available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]
        
        return self.available_tools

    async def get_tools(self) -> List[Dict]:
        """Get list of available tools from the server"""
        if not self.session:
            return []
        response = await self.session.list_tools()
        return [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

    async def get_resources(self) -> List[Dict]:
        """Get list of available resources from the server"""
        if not self.session:
            return []
        try:
            response = await self.session.list_resources()
            return [{
                "uri": resource.uri,
                "name": resource.name,
                "description": getattr(resource, 'description', ''),
                "mime_type": getattr(resource, 'mimeType', 'text/plain')
            } for resource in response.resources]
        except Exception:
            return []

    async def get_prompts(self) -> List[Dict]:
        """Get list of available prompts from the server"""
        if not self.session:
            return []
        try:
            response = await self.session.list_prompts()
            return [{
                "name": prompt.name,
                "description": getattr(prompt, 'description', ''),
                "arguments": getattr(prompt, 'arguments', [])
            } for prompt in response.prompts]
        except Exception:
            return []

    async def read_resource(self, uri: str) -> Dict:
        """Read a specific resource"""
        if not self.session:
            return {"error": "Not connected"}
        try:
            response = await self.session.read_resource(uri)
            return {
                "uri": uri,
                "content": response.contents[0].text if response.contents else ""
            }
        except Exception as e:
            return {"error": str(e)}

    async def get_prompt(self, name: str, arguments: Dict[str, str] = None) -> Dict:
        """Get a prompt with its messages"""
        if not self.session:
            return {"error": "Not connected"}
        try:
            response = await self.session.get_prompt(name, arguments=arguments or {})
            # Convert prompt messages to a usable format
            messages = []
            for msg in response.messages:
                content = msg.content
                # Handle TextContent vs string
                if hasattr(content, 'text'):
                    content = content.text
                elif isinstance(content, list):
                    # Handle list of content blocks
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

    async def process_query(self, query: str) -> MCPMessage:
        """Process a query using Claude and available tools"""
        if not self.session:
            return MCPMessage(role="assistant", content="Not connected to MCP server")

        messages = [{"role": "user", "content": query}]
        tool_calls_made = []

        # Get available tools
        available_tools = await self.get_tools()

        # Initial Claude API call
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=messages,
            tools=available_tools
        )

        # Process response and handle tool calls in a loop
        final_text = []
        
        while response.stop_reason == "tool_use":
            # Collect all tool uses from this response
            assistant_content = []
            tool_results = []
            
            for content in response.content:
                assistant_content.append(content)
                
                if content.type == 'text':
                    final_text.append(content.text)
                elif content.type == 'tool_use':
                    tool_name = content.name
                    tool_args = content.input

                    # Execute tool call
                    result = await self.session.call_tool(tool_name, tool_args)
                    result_text = result.content[0].text if result.content else ""
                    
                    # Record the tool call
                    tool_call = ToolCall(
                        name=tool_name,
                        arguments=tool_args,
                        result=result_text
                    )
                    tool_calls_made.append(tool_call)
                    
                    # Prepare tool result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content.id,
                        "content": result_text
                    })
            
            # Add assistant message with all tool uses
            messages.append({
                "role": "assistant",
                "content": assistant_content
            })
            
            # Add all tool results in a single user message
            messages.append({
                "role": "user",
                "content": tool_results
            })

            # Get next response from Claude
            response = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=messages,
                tools=available_tools
            )
        
        # Process final response (no more tool calls)
        for content in response.content:
            if content.type == 'text':
                final_text.append(content.text)

        return MCPMessage(
            role="assistant",
            content="\n".join(final_text),
            tool_calls=tool_calls_made
        )

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()
        self.connected = False
