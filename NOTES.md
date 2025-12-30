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
