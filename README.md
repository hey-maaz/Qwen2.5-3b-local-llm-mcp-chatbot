# Local MCP Chatbot (Streamlit + Ollama/Qwen + MCP)

## Run
1. Start Ollama and pull a Qwen model that supports tools: `ollama pull qwen3` (or `qwen2.5`).
2. Double-click **run.bat** (it builds its own `.mcpenv` folder; never copy an old `.venv` in) (Windows) or `./run.sh`. First run installs packages automatically.
   Or manually: `pip install -r requirements.txt` then `streamlit run app.py`.

## Files
- `app.py` - Streamlit chat UI + tool-calling loop
- `mcp_server.py` - MCP server (time, calculator, files in `workspace/`, system info)
- `mcp_config.json` - which MCP servers the chatbot connects to
- `workspace/` - the only folder the file tools can read/write

## MCP server
The app auto-starts `mcp_server.py` on http://127.0.0.1:8000/mcp. To run it yourself, double-click
`start_mcp_server.bat` first. If port 8000 is busy, change the port in the sidebar URL.

## Add MCP
- New tool: add a function with `@mcp.tool` in `mcp_server.py`, click **Reload tools**.
- Another MCP server: add it to `mcp_config.json` under `mcpServers`, e.g.
  `"other": {"command": "npx", "args": ["-y", "some-mcp-server"]}`
  (tool names get prefixed with the server name when there are several servers).

## Troubleshooting
- Blank page before: the three source files were empty. Now filled.
- "Cannot reach Ollama": start the Ollama app / `ollama serve`.
- Model ignores tools: use a tool-capable model (qwen3, qwen2.5, llama3.1).

## Still failing?
Double-click `diagnose.bat`, then send the contents of `diagnose.txt`.
