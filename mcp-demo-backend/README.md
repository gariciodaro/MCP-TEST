# Structure

```
mcp-demo-backend/
├── main.py              # 50 lines  - App setup & routing only
├── config.py            # 20 lines  - Settings (API key, CORS)
├── models.py            # 55 lines  - Pydantic schemas
├── mcp_client.py        # 370 lines - MCP client logic
├── routes/
│   ├── __init__.py      # 7 lines   - Exports routers
│   ├── http.py          # 175 lines - REST endpoints
│   └── websocket.py     # 175 lines - WebSocket + elicitation
└── .env
```