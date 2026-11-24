"""
Local chatbot: Streamlit UI + Ollama (Qwen) + MCP tools.

Run:  streamlit run app.py      (or double-click run.bat on Windows)
"""
import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse
from contextlib import AsyncExitStack
from pathlib import Path

import streamlit as st

BASE = Path(__file__).parent.resolve()
CONFIG_FILE = BASE / "mcp_config.json"
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
if not DEFAULT_HOST.startswith("http"):
    DEFAULT_HOST = "http://" + DEFAULT_HOST
MAX_TOOL_ROUNDS = 6

# ---- Draw the page FIRST so it is never blank, even if something fails below ----
st.set_page_config(page_title="Local MCP Chatbot", page_icon="🤖", layout="wide")
st.title("🤖 Local LLM + MCP Chatbot")

try:
    import ollama
    from fastmcp import Client
except ImportError as exc:
    st.error(f"Missing package: {exc.name}")
    st.code(f'"{sys.executable}" -m pip install -r requirements.txt', language="bash")
    st.stop()


# ------------------------------------------------------------------ helpers
def load_mcp_config() -> dict:
    """Read mcp_config.json; make 'python' and relative paths work from any folder."""
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    for server in cfg.get("mcpServers", {}).values():
        if "command" in server:
            if server["command"] in ("python", "python3", "py"):
                server["command"] = sys.executable
            server.setdefault("cwd", str(BASE))
            server["args"] = [
                str(BASE / a) if str(a).endswith(".py") and not os.path.isabs(a) else a
                for a in server.get("args", [])
            ]
    return cfg


@st.cache_resource
def _server_holder() -> dict:
    return {"proc": None}


def ensure_local_server(url: str):
    """Make sure an MCP server answers at `url`; auto-start mcp_server.py if it is local.
    Returns None when OK, otherwise an error message."""
    u = urlparse(url)
    host, port = u.hostname or "127.0.0.1", u.port or 8000

    def up() -> bool:
        try:
            socket.create_connection((host, port), timeout=0.5).close()
            return True
        except OSError:
            return False

    if up():
        return None
    if host not in ("127.0.0.1", "localhost"):
        return f"Cannot reach {url}. Is that server running?"
    holder = _server_holder()
    if holder["proc"] is None or holder["proc"].poll() is not None:
        log = open(BASE / "mcp_server.log", "w", encoding="utf-8")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        holder["proc"] = subprocess.Popen(
            [sys.executable, str(BASE / "mcp_server.py")], cwd=str(BASE),
            env=dict(os.environ, MCP_PORT=str(port)),
            stdout=log, stderr=log, creationflags=flags)
    for _ in range(40):  # wait up to ~20 s
        if up():
            return None
        if holder["proc"].poll() is not None:
            break
        time.sleep(0.5)
    try:
        tail = (BASE / "mcp_server.log").read_text(encoding="utf-8", errors="replace")[-1500:]
    except OSError:
        tail = ""
    return f"MCP server did not start.\n{tail}"


def get_cfg(url: str):
    """URL -> HTTP MCP server; empty -> servers from mcp_config.json (stdio)."""
    return url.strip() if url.strip() else load_mcp_config()


def clean(text: str) -> str:
    """Hide Qwen3 <think>...</think> reasoning blocks."""
    if "<think>" in text and "</think>" not in text:
        return "💭 *thinking…*"
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def result_text(result) -> str:
    parts = [getattr(c, "text", None) for c in getattr(result, "content", []) or []]
    parts = [p for p in parts if p]
    return "\n".join(parts) if parts else str(result)


def list_models(host: str):
    resp = ollama.Client(host=host).list()
    models = getattr(resp, "models", None) or resp.get("models", [])
    names = [getattr(m, "model", None) or m.get("model") or m.get("name") for m in models]
    return sorted(n for n in names if n)


async def fetch_tools(cfg: dict) -> list[dict]:
    async with Client(cfg) as client:
        tools = await client.list_tools()
    out = []
    for t in tools:
        schema = getattr(t, "inputSchema", None) or getattr(t, "input_schema", None) \
            or {"type": "object", "properties": {}}
        out.append({"name": t.name, "description": t.description or "", "schema": schema})
    return out


def to_ollama_tools(tools: list[dict]) -> list[dict]:
    return [
        {"type": "function",
         "function": {"name": t["name"], "description": t["description"], "parameters": t["schema"]}}
        for t in tools
    ]


async def chat_turn(host, model, messages, temperature, cfg, tools, tools_box, answer_ph):
    """Run one user turn: stream the model, execute MCP tool calls, repeat. Returns (text, trace)."""
    oc = ollama.AsyncClient(host=host)
    trace, final_text = [], ""
    use_tools = bool(tools)

    async with AsyncExitStack() as stack:
        mcp_client = await stack.enter_async_context(Client(cfg)) if use_tools else None

        for _ in range(MAX_TOOL_ROUNDS):
            kwargs = dict(model=model, messages=messages, stream=True,
                          options={"temperature": temperature})
            if use_tools:
                kwargs["tools"] = to_ollama_tools(tools)
            try:
                stream = await oc.chat(**kwargs)
            except ollama.ResponseError as exc:
                if use_tools and "tool" in str(exc).lower():
                    use_tools = False
                    tools_box.warning(f"`{model}` does not support tools - answering without MCP.")
                    kwargs.pop("tools", None)
                    stream = await oc.chat(**kwargs)
                else:
                    raise

            text, calls = "", []
            async for chunk in stream:
                msg = chunk.message
                if msg.content:
                    text += msg.content
                    answer_ph.markdown(clean(text) or "…")
                if msg.tool_calls:
                    calls.extend(msg.tool_calls)

            if not calls:
                final_text = clean(text)
                break

            messages.append({
                "role": "assistant", "content": text,
                "tool_calls": [{"function": {"name": c.function.name,
                                             "arguments": dict(c.function.arguments)}} for c in calls],
            })
            for c in calls:
                name, args = c.function.name, dict(c.function.arguments)
                try:
                    res = await mcp_client.call_tool(name, args)
                    out = result_text(res)
                except Exception as exc:
                    out = f"Tool error: {exc}"
                trace.append({"name": name, "args": args, "result": out})
                with tools_box.expander(f"🔧 {name}", expanded=False):
                    st.json(args)
                    st.code(out, language="text")
                messages.append({"role": "tool", "tool_name": name, "content": out})
            answer_ph.markdown("…")
        else:
            final_text = clean(text) or "(stopped: too many tool calls)"

    answer_ph.markdown(final_text)
    return final_text, trace


# ------------------------------------------------------------------ state
ss = st.session_state
ss.setdefault("chat", [])          # [{"role","content","trace"}]
ss.setdefault("tools", None)       # cached MCP tool list
ss.setdefault("tools_err", None)

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    host = st.text_input("Ollama URL", DEFAULT_HOST)

    models, model_err = [], None
    try:
        models = list_models(host)
    except Exception as exc:
        model_err = exc
    if model_err:
        st.error("Cannot reach Ollama. Start it (open the Ollama app or run `ollama serve`).")
        st.caption(str(model_err))
    if not models:
        st.warning("No models found. Run e.g. `ollama pull qwen3` in a terminal.")
    preferred = next((i for i, m in enumerate(models) if "qwen" in m.lower()), 0)
    model = st.selectbox("Model", models, index=preferred if models else None,
                         placeholder="No models available")
    temperature = st.slider("Temperature", 0.0, 1.5, 0.3, 0.1)
    system_prompt = st.text_area(
        "System prompt",
        "You are a helpful assistant running locally. Use the available tools when they help "
        "(math, time, files). Be concise.",
        height=110,
    )

    st.divider()
    use_mcp = st.toggle("Enable MCP tools", value=True)
    mcp_url = st.text_input("MCP Server URL", "http://127.0.0.1:8000/mcp",
                            help="Local URLs are started automatically. Leave empty to use mcp_config.json.")
    if st.button("🔄 Reload tools") or ss.get("tools_url") != mcp_url:
        ss.tools, ss.tools_url = None, mcp_url
    if use_mcp and ss.tools is None:
        try:
            err = ensure_local_server(mcp_url) if mcp_url.strip() else None
            if err:
                raise RuntimeError(err)
            ss.tools = asyncio.run(fetch_tools(get_cfg(mcp_url)))
            ss.tools_err = None
        except Exception as exc:
            ss.tools, ss.tools_err = [], f"{type(exc).__name__}: {exc}"
    if use_mcp:
        if ss.tools_err:
            st.error("MCP server failed to start.")
            st.code(ss.tools_err, language="text")
        elif ss.tools:
            st.success(f"{len(ss.tools)} MCP tools loaded")
            for t in ss.tools:
                with st.expander(t["name"]):
                    st.write(t["description"] or "—")

    st.divider()
    if st.button("🗑️ Clear chat"):
        ss.chat = []
        st.rerun()

# ------------------------------------------------------------------ chat UI
for m in ss.chat:
    with st.chat_message(m["role"]):
        for t in m.get("trace", []):
            with st.expander(f"🔧 {t['name']}"):
                st.json(t["args"])
                st.code(t["result"], language="text")
        st.markdown(m["content"])

if not ss.chat:
    st.info("Ask something, e.g. “What is (123*45)/7 + sqrt(144)?”, “What time is it in Tokyo?”, "
            "or “List the files in your workspace and read hello.txt”.")

prompt = st.chat_input("Type your message…", disabled=not model)
if prompt and model:
    ss.chat.append({"role": "user", "content": prompt, "trace": []})
    with st.chat_message("user"):
        st.markdown(prompt)

    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in ss.chat
    ]
    with st.chat_message("assistant"):
        tools_box = st.container()
        answer_ph = st.empty()
        answer_ph.markdown("…")
        try:
            tools = ss.tools if (use_mcp and ss.tools) else []
            if tools and mcp_url.strip():
                err = ensure_local_server(mcp_url)
                if err:
                    raise RuntimeError(err)
            cfg = get_cfg(mcp_url) if tools else {}
            text, trace = asyncio.run(
                chat_turn(host, model, messages, temperature, cfg, tools, tools_box, answer_ph))
            ss.chat.append({"role": "assistant", "content": text, "trace": trace})
        except Exception as exc:
            answer_ph.error(f"{type(exc).__name__}: {exc}")
            ss.chat.pop()  # drop the unanswered user message
