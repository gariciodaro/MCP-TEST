# MCP Protocol Notes

## Resources vs Tools: Noun vs Verb Analogy

### Resources (Nouns)
- Represent **data entities** that exist
- Like a book on a library shelf
- Can be read/observed without changing them
- Examples: calendar data, documents, user profiles
- URI-addressable: `resource://calendar/today`

### Tools (Verbs)
- Represent **operations/actions** to perform
- Like checking out or returning a book
- Execute functions, may modify data
- Examples: create_event, delete_event, update_meeting

### Key Principle
**Resources = entities with data** (read-focused)  
**Tools = operations/actions** (write/modify-focused)

---

## User Interaction Model for Resources

### Core Concept: Application-Driven Design
The MCP protocol **doesn't dictate UI** - it only defines how servers expose resources. Each client application decides how to present them to users.

### Common Interaction Patterns

#### 1. Tree or List Views
Resources displayed in hierarchical structures, like file explorers:
```
📁 Database Resources
  └─ 📊 users_table
  └─ 📊 orders_table
📁 API Resources  
  └─ 🌐 current_weather
  └─ 🌐 forecast
```
**Use case**: Natural parent-child relationships (folders, databases, categories)

#### 2. Search and Filter Interfaces
Users type to find specific resources:
```
Search: "customer data"
Results:
  ✓ database://customers
  ✓ api://customer_analytics  
```
**Use case**: Large number of resources where browsing is inefficient

#### 3. Automatic Context Inclusion
The application **intelligently decides** which resources to include without user action.

**Example**: 
- User asks "What's in my calendar?"
- App automatically fetches `resource://calendar/today`
- User never manually selected it

**Driven by**:
- Heuristics: Keywords in conversation trigger resource inclusion
- AI selection: LLM decides which resources are relevant

#### 4. Manual Selection
User explicitly chooses resources:
```
☐ Include database schema
☑ Include API documentation  
☐ Include error logs
```
**Use case**: Precise control over context

#### 5. Bulk Selection
Select multiple resources at once:
```
Select all: "*.log"
✓ app.log
✓ error.log  
[Add to Context]
```

### Why This Flexibility Matters

**Different Contexts Need Different UIs**:
- Code editor: Tree view matches file explorer mental model
- Chat app: Search/suggestions fit conversational flow
- Dashboard: Bulk selection for data analysis

**Protocol's Role**: Provides resource discovery (`resources/list`), reading (`resources/read`), and metadata. The **application** builds the UI.

### Summary
- MCP servers expose resources (the "what")
- Client applications decide presentation (the "how")
- No mandatory UI patterns
- Protocol is **UI-agnostic** by design

---

## Prompts: Structured Templates vs Natural Language

### MCP Architecture (3 Actors)
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

### Two Interaction Patterns

#### Pattern 1: Natural Language (Free-Form)
```
User types freely → LLM interprets → Makes MCP calls

Example:
User: "What's my calendar for today?"
→ LLM calls: resources/read(uri="calendar://today")
```

**Characteristics**:
- Flexible, conversational
- LLM must interpret intent
- Varies by user phrasing
- Good for ad-hoc questions

#### Pattern 2: Prompt Templates (Structured)
```
User selects prompt → Fills form → Structured input → LLM processes → Makes MCP calls

Example:
User: Selects "/plan-vacation"
Form: Destination [Barcelona], Duration [7], Budget [3000]
→ LLM receives well-structured context
```

**Characteristics**:
- Consistent data structure
- Required fields enforced
- Type validation
- Better for repetitive workflows

### Key Insight: Prompts Help the LLM, Don't Replace It

**Prompts are NOT pre-programmed scripts** - they're **UI scaffolding + input structuring**.

The LLM still:
- Decides which MCP tools/resources to call
- Processes the request
- Generates responses

Prompts just provide **better structured context**.

### Comparison Table

| Aspect | Natural Language | Prompt Template |
|--------|------------------|-----------------|
| **User Input** | Free text | Structured form |
| **LLM Input** | Raw user text | Formatted template + data |
| **Consistency** | Varies | Same structure every time |
| **Best For** | Ad-hoc queries | Repetitive tasks |
| **Discoverability** | Must know what to ask | Browse available prompts |
| **Validation** | None | Type/required field checks |

### When to Use Each

**Use Natural Language**:
- Ad-hoc questions: "What's the weather?"
- Exploratory conversation
- Quick, one-off requests
- Power users who know what they want

**Use Prompts**:
- Repetitive workflows
- Complex multi-step processes
- Form-like data entry
- Onboarding new users
- When consistency matters

**Best Practice**: Use **both** - natural language for exploration, prompts for structured workflows.

### Prompts Are Optional
You can build a fully functional MCP server without any prompts, relying entirely on natural language + tools/resources.

---

## MCP Client Components

### Key Distinction
**Host Application** (e.g., Claude Desktop, VS Code) manages the user experience and coordinates multiple **MCP Clients**. Each client handles communication with one server.

### Core Client Features

MCP clients provide three special features that **servers can request**:

#### 1. **Elicitation** - Ask Users for Missing Info
Servers can pause and request specific information from users dynamically.

**Example**: A travel booking server needs final confirmation
- Server asks: "Confirm Barcelona booking? Seat preference? Travel insurance?"
- User fills structured form
- Server continues with confirmed details

**Key Point**: Flexible workflows that adapt to user needs, not rigid pre-defined paths.

---

#### 2. **Roots** - Communicate Filesystem Boundaries
Clients tell servers which directories they can access (advisory, not security).

**Example**: Travel agent workspace
- Client exposes: `file:///Users/agent/travel-planning`
- Client exposes: `file:///Users/agent/travel-templates`
- Well-behaved servers respect these boundaries

**Key Point**: Coordination mechanism for scoping work, preventing accidents. Not security enforcement.

---

#### 3. **Sampling** - Request AI Completions
Servers ask clients to run LLM tasks on their behalf (server doesn't need own AI access).

**Example**: Flight recommendation tool
- Server gathers 47 flight options
- Server requests: "Analyze these flights and recommend best one"
- Client's LLM evaluates options
- User reviews AI response before it returns to server

**Key Point**: Human-in-the-loop AI tasks. Client controls security, permissions, and model access.

---

### Summary Table

| Feature | Purpose | Example |
|---------|---------|---------|
| **Elicitation** | Get missing info from users | "Which seat preference?" |
| **Roots** | Define filesystem scope | "Work in this directory" |
| **Sampling** | Request AI assistance | "Analyze this data for me" |

**Remember**: These are **server-to-client requests** - servers ask clients for help, and clients maintain user control.

---
# Local test MCP server + claude Desktop

+ code $env:AppData\Claude\claude_desktop_config.json   

```powershell
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "G:\\mcp-file-system-folder"
      ]
    },
    "weather": {
      "command": "C:\\ProgramData\\anaconda3\\Scripts\\conda.exe",
      "args": [
        "run",
        "-n",
        "mcp",
        "--no-capture-output",
        "python",
        "F:\\my-code\\MCP-TEST\\weather-mcp\\weather.py"
      ]
    }
  }
}
```

# Local test MCP server + MCP client (local chat test)
`python client.py F:\my-code\MCP-TEST\weather-mcp-server\weather.py`