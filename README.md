# MCP Demo Project

A practical demonstration of the **Model Context Protocol (MCP)** - showing how to build **MCP Servers** and **MCP Clients** for AI applications.

## What is MCP?

MCP is a protocol that standardizes how AI applications communicate with external data and tools. It has two sides:

- **MCP Server** - Exposes capabilities (tools, resources, prompts) for AI to use
- **MCP Client** - Lives in your AI application, connects to servers, orchestrates LLM + tools

```
┌─────────────────────────────────────┐
│   Your AI Application               │
│   ┌─────────────────────────────┐   │
│   │  MCP Client                 │   │
│   │  - Connects to MCP servers  │   │
│   │  - Manages tool execution   │   │
│   │  - Orchestrates with LLM    │   │
│   └──────────────┬──────────────┘   │
└──────────────────┼──────────────────┘
                   │ MCP Protocol
                   ▼
┌─────────────────────────────────────┐
│   MCP Server                        │
│   - Exposes Tools, Resources,       │
│     Prompts                         │
└─────────────────────────────────────┘
```

### Who is this for?

If you're building or maintaining **AI-powered applications**, you need to understand both:
- **Building servers** to expose your APIs/data to AI
- **Building clients** to connect your AI app to MCP servers

## Project Structure

```
MCP-TEST/
├── weather-mcp-server/     # MCP Server (Python + FastMCP)
│   └── weather.py          # Exposes weather tools, resources, prompts
├── mcp-demo-backend/       # MCP Client + API (FastAPI)
│   ├── main.py             # REST endpoints
│   └── mcp_client.py       # Connects to MCP server + Anthropic API
├── mcp-demo-frontend/      # Web UI (Vite + React)
│   └── src/App.jsx         # Chat interface with MCP features
└── imgs/                   # Screenshots
```

---

# MCP Server Features

The MCP server exposes three core feature types. Here's how each works in practice:

## 1. Tools 🔧
**Actions the AI can execute** - like API calls or functions.

Tools let the AI *do things*. When you ask "What's the weather in NYC?", the AI calls the `get_forecast` tool with coordinates.

```python
@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location."""
    # Calls National Weather Service API
    # Returns formatted forecast
```

![Tools Demo](imgs/tools.png)

**In the UI:** Ask a question → AI decides to use a tool → Tool executes → AI summarizes the result.

---

## 2. Resources 📦
**Data the AI can read** - static or dynamic information.

Resources are like files or documents the AI can access. They're read-only and URI-addressable.

```python
@mcp.resource("weather://supported-states")
def get_supported_states() -> str:
    """List of all supported US state codes."""
    return "AL: Alabama, AK: Alaska, ..."

@mcp.resource("weather://example-cities")
def get_example_cities() -> str:
    """Cities with pre-loaded coordinates."""
    return "New York: 40.7128, -74.0060 ..."
```

![Resources Demo](imgs/resources.png)

**In the UI:** Click a resource → See its content. The AI can also read these to get context.

---

## 3. Prompts 📝
**Pre-built conversation starters** - structured input templates.

Prompts guide users through common workflows with forms instead of free text.

```python
@mcp.prompt()
def weekly_planning(city: str) -> str:
    """Get a detailed weather summary for weekly planning."""
    return f"""I need to plan my week in {city}. 
    Please get the forecast and any alerts, then provide:
    1. Day-by-day breakdown
    2. Best days for outdoor activities
    3. Clothing recommendations"""
```

![Prompts Demo](imgs/prompts.png)

**In the UI:** Select a prompt → Fill in arguments → Preview → Use in chat.

---

# Quick Start

## Prerequisites
- Python 3.11+ with conda
- Node.js 18+
- Anthropic API key

## 1. Set up the MCP Server

```bash
cd weather-mcp-server
conda activate mcp
# Server runs via stdio, started automatically by the client
```

## 2. Start the Backend

```bash
cd mcp-demo-backend
# Create .env with your API key
echo ANTHROPIC_API_KEY=your-key-here > .env

conda activate mcp
uvicorn main:app --reload --port 8000
```

## 3. Start the Frontend

```bash
cd mcp-demo-frontend
npm install
npm run dev
# Open http://localhost:5173
```

## 4. Connect & Test

1. Click **Connect** in the UI
2. Try: *"What's the weather forecast for NYC?"*
3. Watch the AI use the `get_forecast` tool
4. Explore Resources and Prompts tabs

---

# Key Concepts

| Feature | What it is | Analogy |
|---------|------------|---------|
| **Tools** | Actions to execute | Verbs - *"do something"* |
| **Resources** | Data to read | Nouns - *"get information"* |
| **Prompts** | Structured templates | Forms - *"guided workflow"* |

---

# Next Steps

- [ ] Add MCP Client features (Elicitation, Roots, Sampling)
- [ ] Add more tools (calendar, email, etc.)
- [ ] Deploy to production

---

## Resources

- 📘 **[NOTES.md](NOTES.md)** - Detailed MCP concepts, architecture diagrams, and implementation notes
- [MCP Documentation](https://modelcontextprotocol.io/)
- [FastMCP Python SDK](https://github.com/jlowin/fastmcp)
- [Anthropic API](https://docs.anthropic.com/)
