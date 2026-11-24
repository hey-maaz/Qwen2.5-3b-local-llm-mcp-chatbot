"""
Local MCP server (stdio) used by the Streamlit chatbot.

The chatbot launches this file automatically (HTTP on http://127.0.0.1:8000/mcp).
You can also run it by hand:  python mcp_server.py   (add --stdio for stdio mode)
To add your own tool, write a function and decorate it with @mcp.tool.

IMPORTANT: never print() to stdout in this file - stdout is the MCP channel.
"""
import ast
import math
import operator
import platform
from datetime import datetime
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("Local Tools")

# Files the bot may touch are restricted to this folder.
WORKSPACE = (Path(__file__).parent / "workspace").resolve()
WORKSPACE.mkdir(exist_ok=True)


def _safe_path(rel: str) -> Path:
    p = (WORKSPACE / rel).resolve()
    if p != WORKSPACE and WORKSPACE not in p.parents:
        raise ValueError("Path is outside the workspace folder.")
    return p


# ---------- safe calculator ----------
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}
_FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "abs": abs, "round": round,
    "floor": math.floor, "ceil": math.ceil,
}
_CONSTS = {"pi": math.pi, "e": math.e}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        if isinstance(node.op, ast.Pow) and abs(_eval(node.right)) > 1000:
            raise ValueError("Exponent too large.")
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCS and not node.keywords):
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError("Unsupported expression.")


# ---------- tools ----------
@mcp.tool
def get_current_time(timezone: str = "local") -> str:
    """Get the current date and time. `timezone` is an IANA name such as
    'Asia/Kolkata' or 'UTC'; use 'local' for this computer's local time."""
    try:
        if timezone.lower() == "local":
            now = datetime.now().astimezone()
        else:
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo(timezone))
        return now.strftime("%A, %d %B %Y, %H:%M:%S %Z (UTC%z)")
    except Exception as exc:
        return f"Could not get time for '{timezone}': {exc}"


@mcp.tool
def calculate(expression: str) -> str:
    """Evaluate a math expression exactly, e.g. '(12.5 * 8) / 3 + sqrt(16)'.
    Supports + - * / // % **, parentheses, pi, e, sqrt, sin, cos, tan, log,
    log10, abs, round, floor, ceil. Use this instead of doing math yourself."""
    try:
        result = _eval(ast.parse(expression.strip(), mode="eval"))
        return f"{expression} = {result}"
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool
def list_files(subfolder: str = "") -> str:
    """List files and folders inside the chatbot's workspace folder."""
    try:
        base = _safe_path(subfolder)
        if not base.is_dir():
            return f"'{subfolder}' is not a folder."
        items = sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        if not items:
            return "(empty)"
        return "\n".join(
            f"{'[dir] ' if p.is_dir() else '      '}{p.relative_to(WORKSPACE)}" for p in items
        )
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool
def read_file(path: str) -> str:
    """Read a UTF-8 text file from the workspace folder (first 20,000 characters)."""
    try:
        p = _safe_path(path)
        if not p.is_file():
            return f"File not found: {path}"
        text = p.read_text(encoding="utf-8", errors="replace")
        return text[:20000] + ("\n...[truncated]" if len(text) > 20000 else "")
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool
def write_file(path: str, content: str, append: bool = False) -> str:
    """Create or overwrite (or append to) a text file in the workspace folder."""
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a" if append else "w", encoding="utf-8") as fh:
            fh.write(content)
        return f"{'Appended to' if append else 'Wrote'} {path} ({len(content)} characters)."
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool
def system_info() -> str:
    """Basic information about the computer running the chatbot."""
    return (f"OS: {platform.system()} {platform.release()}\n"
            f"Machine: {platform.machine()}\n"
            f"Python: {platform.python_version()}")


if __name__ == "__main__":
    import os
    import sys

    if "--stdio" in sys.argv:
        mcp.run(show_banner=False)  # stdio transport
    else:
        # HTTP transport -> endpoint http://127.0.0.1:8000/mcp
        mcp.run(transport="http", host="127.0.0.1",
                port=int(os.environ.get("MCP_PORT", "8000")), show_banner=False)
