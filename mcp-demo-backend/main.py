"""
MCP Demo API - Main Application Entry Point.

This is a demonstration of Model Context Protocol (MCP) features including:
- Tools, Resources, and Prompts via REST API
- Real-time chat with Elicitation support via WebSocket

Run with: uvicorn main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from routes import http_router, websocket_router
from routes.http import startup as http_startup, shutdown as http_shutdown

# Configure logging to show our debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    await http_startup()
    yield
    await http_shutdown()


app = FastAPI(
    title="MCP Demo API",
    description="Demo API for Model Context Protocol features",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(http_router)
app.include_router(websocket_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
