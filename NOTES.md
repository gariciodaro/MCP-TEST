# MCP Protocol Notes

## MCP Architecture Overview
```
┌─────────────────────────────────────┐
│   AI Application (e.g., Claude)    │
│   - Hosts the MCP Client            │
│   - Contains the LLM                │
│   - User interacts here             │
└──────────────┬──────────────────────┘
               │ MCP Protocol
               ▼
┌─────────────────────────────────────┐
│   MCP Server (Your Code)            │
│   - Exposes Resources/Tools/Prompts │
└─────────────────────────────────────┘
```

---

# MCP Server

## Definition
An **MCP Server** is a program that exposes capabilities (data and functionality) to AI applications through the MCP protocol. Servers provide context and tools that LLMs can use to accomplish tasks.

**You build servers** to connect your data, APIs, and services to AI applications.

---

## Core Server Features

### 1. Tools (Verbs) 🔧
**Actions the LLM can execute** - functions that do something.

- Represent **operations/actions** to perform
- Like checking out or returning a book from a library
- Execute functions, may modify data or have side effects
- Examples: `create_event`, `send_email`, `query_database`

```python
@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location."""
    # ... fetch and return weather data
```

---

### 2. Resources (Nouns) 📦
**Data the LLM can read** - information that exists.

- Represent **data entities** that exist
- Like a book on a library shelf
- Can be read/observed without changing them
- URI-addressable: `resource://calendar/today`
- Examples: calendar data, documents, user profiles

```python
@mcp.resource("weather://supported-states")
def get_supported_states() -> str:
    """List of all supported US state codes."""
    return "CA, NY, TX, ..."
```

#### How to Make Resources Available to the LLM

Resources are exposed by the server, but **how** the client provides them to the LLM is an implementation choice. Three main approaches:

##### Approach 1: Auto-inject as Context
Automatically fetch all (or relevant) resources and include them in the system prompt.

```
┌─────────────────────────────────────────────┐
│ System Prompt:                              │
│ "You have access to this context:           │
│  [weather://supported-states content]       │
│  [weather://example-cities content]"        │
├─────────────────────────────────────────────┤
│ User: "What states support weather alerts?" │
└─────────────────────────────────────────────┘
```

| Pros | Cons |
|------|------|
| Simple to implement | Wastes tokens if resources are large/irrelevant |
| LLM always has full context | No selectivity - all resources loaded every time |
| No extra user interaction | Doesn't scale with many resources |

**Best for:** Small, always-relevant datasets (config, reference data)

##### Approach 2: LLM Requests Resources (Resource as Tool)
Expose a tool like `read_resource(uri)` that the LLM can call when it needs information.

```
User: "What cities have pre-loaded coordinates?"
    ↓
LLM thinks: "I need the example-cities resource"
LLM calls: read_resource("weather://example-cities")
    ↓
Client: fetches resource, returns content
    ↓
LLM: summarizes and responds
```

| Pros | Cons |
|------|------|
| Token efficient (on-demand) | Extra round-trip for LLM to decide |
| Scales to many resources | LLM might not know what resources exist |
| LLM reasons about what it needs | Requires listing available resources somehow |

**Best for:** Large knowledge bases, dynamic data, many resources

**Where does this tool live?** On the **MCP Client**, not the server.

```
┌─────────────────────────────────────────────────────────┐
│  AI Application                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  MCP Client                                       │  │
│  │  • Gets tools from servers → sends to LLM        │  │
│  │  • Gets resources list from servers              │  │
│  │                                                   │  │
│  │  ★ Creates SYNTHETIC tool: read_resource(uri)    │  │
│  │    - Not from any server                          │  │
│  │    - Client intercepts this call                  │  │
│  │    - Client uses MCP protocol to fetch resource   │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                        │ MCP Protocol (already has resources/read)
                        ▼
┌─────────────────────────────────────────────────────────┐
│  MCP Server                                             │
│  • Exposes tools (get_forecast, get_alerts)            │
│  • Exposes resources (weather://supported-states)       │
│  • Does NOT need a "read_resource" tool                 │
└─────────────────────────────────────────────────────────┘
```

**Why on the client, not server?**
- MCP protocol **already** has `resources/read` - servers don't need to duplicate it as a tool
- Client already knows how to read resources via protocol
- Works across **all** servers without each implementing it
- Client controls what tools the LLM sees

---
User explicitly selects which resources to include before or during chat (like attaching files).

```
UI: ☑ supported-states  ☑ example-cities  ☐ api-info

User selects, then asks → Client includes selected resources as context
```

| Pros | Cons |
|------|------|
| User controls exactly what's included | Requires user to understand resources |
| Transparent - user sees what AI "knows" | Extra friction before chatting |
| Works for focused tasks | User might forget relevant context |

**Best for:** Document-heavy workflows, expert users, compliance scenarios

##### Comparison Summary

| Approach | Who Decides? | Token Usage | User Effort | Best For |
|----------|--------------|-------------|-------------|----------|
| **Auto-inject** | System | High | None | Small reference data |
| **LLM requests** | AI | Efficient | None | Large knowledge bases |
| **User selects** | Human | Controlled | Manual | Transparency, experts |

**Hybrid approaches** are also valid:
- Auto-inject essentials + LLM requests extras
- User selects initial context + LLM can dig deeper
- Smart auto-inject based on query analysis

---

### 3. Prompts (Templates) 📝
**Structured conversation starters** - pre-defined workflows.

- **Optional** - not required for a functional server
- UI scaffolding + input structuring for the LLM
- Ensure consistent, validated user input
- Good for repetitive tasks and onboarding new users

```python
@mcp.prompt()
def plan_vacation(destination: str, days: int) -> str:
    """Guide through vacation planning."""
    return f"Plan a {days}-day trip to {destination}..."
```

---

### Key Principle: Nouns vs Verbs

| Aspect | Resources (Nouns) | Tools (Verbs) |
|--------|-------------------|---------------|
| **Purpose** | Data to read | Actions to perform |
| **Analogy** | Book on shelf | Checking out a book |
| **Side Effects** | None (read-only) | May modify data |
| **Examples** | `weather://alerts` | `send_email()` |

---

### Prompts vs Natural Language

| Aspect | Natural Language | Prompt Template |
|--------|------------------|-----------------|
| **User Input** | Free text | Structured form |
| **Consistency** | Varies by phrasing | Same structure every time |
| **Best For** | Ad-hoc queries | Repetitive tasks |
| **Validation** | None | Type/required field checks |

**Best Practice**: Use **both** - natural language for exploration, prompts for structured workflows.

---

# MCP Client

## Definition
An **MCP Client** is the component (inside a host application like Claude Desktop or VS Code) that connects to MCP servers and makes their capabilities available to the LLM.

**Host Application** manages user experience and coordinates multiple **MCP Clients**. Each client handles communication with one server.

**You usually don't build clients** - you use existing ones (Claude Desktop, VS Code) to connect to your servers.

---

## Core Client Features

These are features that **servers can request from clients** (server-to-client requests):

### 1. Elicitation 💬
**Ask users for missing information** during server operations.

- Servers can pause and request specific info from users dynamically
- Creates flexible workflows that adapt to user needs
- User fills structured form, server continues with data

**Example**: Travel booking server needs final confirmation
- Server asks: "Confirm Barcelona booking? Seat preference? Travel insurance?"
- User fills structured form
- Server continues with confirmed details

**Key Point**: Flexible workflows, not rigid pre-defined paths.

---

### 2. Roots 📁
**Communicate filesystem boundaries** to servers.

- Clients tell servers which directories they can access
- Advisory mechanism, not security enforcement
- Helps scope work and prevent accidents

**Example**: Travel agent workspace
- Client exposes: `file:///Users/agent/travel-planning`
- Client exposes: `file:///Users/agent/travel-templates`
- Well-behaved servers respect these boundaries

**Key Point**: Coordination for scoping work. Not a security boundary.

---

### 3. Sampling 🤖
**Request AI completions** through the client.

- Servers ask clients to run LLM tasks on their behalf
- Server doesn't need its own AI/API access
- Human-in-the-loop: user reviews AI response before it returns to server

**Example**: Flight recommendation tool
- Server gathers 47 flight options
- Server requests: "Analyze these flights and recommend best one"
- Client's LLM evaluates options
- User reviews AI response before it returns to server

**Key Point**: Client controls security, permissions, and model access.

---

### Summary Table

| Feature | Direction | Purpose | Example |
|---------|-----------|---------|---------|
| **Elicitation** | Server → Client | Get missing info from users | "Which seat preference?" |
| **Roots** | Client → Server | Define filesystem scope | "Work in this directory" |
| **Sampling** | Server → Client | Request AI assistance | "Analyze this data for me" |

---

# Additional Notes

## User Interaction Model for Resources

The MCP protocol **doesn't dictate UI** - each client application decides how to present resources:

- **Tree/List Views**: Hierarchical file-explorer style
- **Search/Filter**: Type to find resources
- **Auto-inclusion**: AI decides which resources are relevant
- **Manual Selection**: User explicitly chooses resources
- **Bulk Selection**: Select multiple resources at once

Protocol is **UI-agnostic** by design.

---

# Local Setup Reference

## Claude Desktop Config
```powershell
code $env:AppData\Claude\claude_desktop_config.json
```

```json
{
  "mcpServers": {
    "weather": {
      "command": "C:\\ProgramData\\anaconda3\\Scripts\\conda.exe",
      "args": [
        "run", "-n", "mcp", "--no-capture-output",
        "python", "F:\\my-code\\MCP-TEST\\weather-mcp-server\\weather.py"
      ]
    }
  }
}
```

## Local MCP Client Test
```powershell
python client.py F:\my-code\MCP-TEST\weather-mcp-server\weather.py
```

---

# Troubleshooting: Issues Encountered Building the Demo

This section documents issues we encountered while building the MCP demo with WebSocket elicitation support.

---

## Issue 1: PromptArgument Not JSON Serializable

**Error:**
```
"Object of type PromptArgument is not JSON serializable"
```

**Cause:** `list_prompts()` returned raw MCP SDK `PromptArgument` objects instead of plain dicts.

**Solution:** Convert each argument to a dict:
```python
"arguments": [
    {
        "name": arg.name,
        "description": getattr(arg, 'description', ''),
        "required": getattr(arg, 'required', False)
    }
    for arg in getattr(prompt, 'arguments', []) or []
]
```

**File:** `mcp_client.py` - `list_prompts()` method

---

## Issue 2: Tool Output Not JSON Serializable

**Error:**
```
"Object of type get_forecastOutput is not JSON serializable"
```

**Cause:** FastMCP client returns typed result objects (e.g., `get_forecastOutput`) instead of plain strings when using elicitation support.

**Solution:** Handle various result types in `_call_tool_with_elicitation()`:
```python
if hasattr(result, 'data'):
    data = result.data
    if isinstance(data, str):
        return data
    elif hasattr(data, 'model_dump_json'):
        return data.model_dump_json()  # Pydantic model
    elif hasattr(data, '__dict__'):
        return json.dumps(data.__dict__, default=str)  # Dataclass
    else:
        return str(data)
```

**File:** `mcp_client.py` - `_call_tool_with_elicitation()` method

---

## Issue 3: ctx.elicit() Wrong Parameter Name

**Error:**
```
"Context.elicit() got an unexpected keyword argument 'response_type'"
```

**Cause:** The MCP server's `Context.elicit()` method uses `schema=` parameter, not `response_type=`.

**Solution:** Change the call in weather.py:
```python
# Wrong
result = await ctx.elicit(message="...", response_type=TripDetails)

# Correct
result = await ctx.elicit(message="...", schema=TripDetails)
```

**File:** `weather-mcp-server/weather.py` - `plan_trip()` tool

---

## Issue 4: Elicitation Schema Must Be Pydantic Model

**Cause:** MCP specification requires elicitation schemas to be Pydantic models (not dataclasses). The server validates that only primitive types are used.

**Solution:** Change from dataclass to Pydantic BaseModel:
```python
# Wrong
@dataclass
class TripDetails:
    travel_date: str
    num_days: int
    activities: str

# Correct
from pydantic import BaseModel

class TripDetails(BaseModel):
    travel_date: str
    num_days: int
    activities: str
```

**File:** `weather-mcp-server/weather.py`

---

## Issue 5: ElicitResult Uses `content`, Not `data`

**Cause:** The MCP protocol's `ElicitResult` expects `content=` for accepted data, not returning a raw dict.

**Solution:** Return proper `ElicitResult` with content field:
```python
# Wrong
if action == "accept":
    return response.get("data", {})

# Correct
if action == "accept":
    return ElicitResult(action="accept", content=data)
```

**Note:** The `content` field expects `dict[str, Union[str, int, float, bool, list[str], None]]` - a dict of primitives only.

**File:** `mcp_client.py` - `elicitation_handler`

---

## Issue 6: WebSocket Elicitation Deadlock (CRITICAL!)

**Error:** Elicitation always timed out immediately, user response came too late.

**Symptoms in logs:**
```
22:00:00,838 - elicitation_handler: timeout
22:00:06,565 - resolve_elicitation: response={...}
22:00:06,565 - No pending elicitation or already done!
```

**Root Cause:** Classic async deadlock:

```
handle_messages() 
  → handle_chat() 
    → process_query() 
      → call_tool() 
        → handle_elicitation() 
          → waits on Future...
```

The main message loop (`handle_messages`) was blocked inside `handle_chat`, waiting for `process_query` to finish. But `process_query` was waiting for elicitation response. The only way to receive that response was through the blocked `handle_messages` loop - **DEADLOCK**.

**Solution:** `handle_elicitation` must receive WebSocket messages directly while waiting, instead of using a Future that the blocked main loop would resolve:

```python
async def handle_elicitation(self, message: str, schema: dict) -> dict:
    await self.send({
        "type": "elicitation",
        "message": message,
        "schema": schema
    })
    
    # Receive messages directly here since main loop is blocked
    start_time = asyncio.get_event_loop().time()
    timeout = 120
    
    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= timeout:
            return {"action": "cancel", "reason": "timeout"}
        
        try:
            data = await asyncio.wait_for(
                self.websocket.receive_json(),
                timeout=min(timeout - elapsed, 30)
            )
            
            if data.get("type") == "elicitation_response":
                return {
                    "action": data.get("action", "cancel"),
                    "data": data.get("data", {})
                }
        except asyncio.TimeoutError:
            continue
```

**Key Insight:** When you have a request-response pattern inside an already-blocked async chain, you can't rely on the outer loop to receive the response. The inner function must handle its own I/O.

**File:** `routes/websocket.py` - `handle_elicitation()` method

---

## Why WebSocket for Elicitation?

HTTP is request-response: client sends request, server sends ONE response, done. 

Elicitation requires:
1. Client sends chat message
2. Server starts processing, tool needs user input
3. Server sends elicitation request **mid-processing**
4. Client responds with user input
5. Server continues processing
6. Server sends final response

This is impossible with HTTP - you can't send multiple responses to one request.

---

## FastMCP Client vs Standard MCP Client

- **Standard `ClientSession`**: No elicitation support, simpler
- **FastMCP `Client`**: Supports `elicitation_handler` callback for tools that use `ctx.elicit()`

We use FastMCP client when elicitation is needed, standard client otherwise.

---

## Logging in Uvicorn

Regular `print()` statements may be buffered. Use Python's `logging` module with WARNING or higher level:

```python
import logging
logger = logging.getLogger(__name__)
logger.warning("This will show in uvicorn output")
```

Configure in main.py:
```python
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

---

## Key Learnings

1. **MCP SDK objects aren't JSON-serializable** - always convert to dicts
2. **Pydantic vs Dataclass** - MCP elicitation requires Pydantic models
3. **Async deadlocks are subtle** - trace the full call chain when debugging
4. **WebSocket message loops** - be careful what blocks them
5. **Read the actual API signatures** - parameter names matter (`schema` vs `response_type`)
