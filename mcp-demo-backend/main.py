import os
import asyncio
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from mcp_client import MCPClient, ToolCall

load_dotenv()

# Global MCP client instance
mcp_client: Optional[MCPClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global mcp_client
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your-api-key-here":
        print("WARNING: ANTHROPIC_API_KEY not set in .env file")
    else:
        mcp_client = MCPClient(api_key)
    
    yield
    
    # Cleanup on shutdown
    if mcp_client:
        await mcp_client.cleanup()


app = FastAPI(
    title="MCP Demo API",
    description="Demo API for Model Context Protocol features",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class ConnectRequest(BaseModel):
    server_path: str


class ChatRequest(BaseModel):
    message: str


class ToolCallResponse(BaseModel):
    name: str
    arguments: Dict[str, Any]
    result: str


class ChatResponse(BaseModel):
    response: str
    tool_calls: List[ToolCallResponse]


class ServerStatus(BaseModel):
    connected: bool
    server_path: Optional[str] = None
    tools: List[Dict] = []
    resources: List[Dict] = []
    prompts: List[Dict] = []


class ResourceReadRequest(BaseModel):
    uri: str


# API Endpoints
@app.get("/")
async def root():
    return {"message": "MCP Demo API", "status": "running"}


@app.get("/status", response_model=ServerStatus)
async def get_status():
    """Get current MCP server connection status"""
    if not mcp_client or not mcp_client.connected:
        return ServerStatus(connected=False)
    
    tools = await mcp_client.get_tools()
    resources = await mcp_client.get_resources()
    prompts = await mcp_client.get_prompts()
    
    return ServerStatus(
        connected=True,
        tools=tools,
        resources=resources,
        prompts=prompts
    )


@app.post("/connect")
async def connect_to_server(request: ConnectRequest):
    """Connect to an MCP server"""
    global mcp_client
    
    if not mcp_client:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key or api_key == "your-api-key-here":
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
        mcp_client = MCPClient(api_key)
    
    # Disconnect if already connected
    if mcp_client.connected:
        await mcp_client.cleanup()
        mcp_client = MCPClient(os.getenv("ANTHROPIC_API_KEY"))
    
    try:
        tools = await mcp_client.connect_to_server(request.server_path)
        resources = await mcp_client.get_resources()
        prompts = await mcp_client.get_prompts()
        
        return {
            "status": "connected",
            "server_path": request.server_path,
            "tools": tools,
            "resources": resources,
            "prompts": prompts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/disconnect")
async def disconnect_from_server():
    """Disconnect from the MCP server"""
    global mcp_client
    
    if mcp_client and mcp_client.connected:
        await mcp_client.cleanup()
        mcp_client = MCPClient(os.getenv("ANTHROPIC_API_KEY"))
        return {"status": "disconnected"}
    
    return {"status": "not_connected"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message and get a response using MCP tools"""
    if not mcp_client or not mcp_client.connected:
        raise HTTPException(status_code=400, detail="Not connected to MCP server")
    
    try:
        result = await mcp_client.process_query(request.message)
        
        tool_calls = [
            ToolCallResponse(
                name=tc.name,
                arguments=tc.arguments,
                result=tc.result if isinstance(tc.result, str) else str(tc.result)
            )
            for tc in result.tool_calls
        ]
        
        return ChatResponse(
            response=result.content,
            tool_calls=tool_calls
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools")
async def get_tools():
    """Get list of available tools"""
    if not mcp_client or not mcp_client.connected:
        raise HTTPException(status_code=400, detail="Not connected to MCP server")
    
    tools = await mcp_client.get_tools()
    return {"tools": tools}


@app.get("/resources")
async def get_resources():
    """Get list of available resources"""
    if not mcp_client or not mcp_client.connected:
        raise HTTPException(status_code=400, detail="Not connected to MCP server")
    
    resources = await mcp_client.get_resources()
    return {"resources": resources}


@app.post("/resources/read")
async def read_resource(request: ResourceReadRequest):
    """Read a specific resource"""
    if not mcp_client or not mcp_client.connected:
        raise HTTPException(status_code=400, detail="Not connected to MCP server")
    
    result = await mcp_client.read_resource(request.uri)
    return result


@app.get("/prompts")
async def get_prompts():
    """Get list of available prompts"""
    if not mcp_client or not mcp_client.connected:
        raise HTTPException(status_code=400, detail="Not connected to MCP server")
    
    prompts = await mcp_client.get_prompts()
    return {"prompts": prompts}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
