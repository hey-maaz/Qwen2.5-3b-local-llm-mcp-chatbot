# Local LLM + MCP Chatbot

A simple chatbot that runs fully on your own computer. It uses a local Qwen
model through Ollama, a Streamlit web interface, and the Model Context
Protocol (MCP) so the model can use real tools.

Built for teaching: students can see how an AI decides to call a tool,
and then build their own.

## What it can do
- Chat with a local Qwen model (no cloud, no API key)
- Call MCP tools: calculator, current time, read and write files in a safe folder
- Show every tool call (name, arguments, result) inside the chat
- Connect to online MCP servers such as GitHub using a personal access token
- Let you choose which tools the model can use

## How it works
1. You ask a question in the Streamlit app (the MCP client).
2. Qwen decides whether it needs a tool.
3. The MCP server runs the tool and returns the result.
4. Qwen uses the result to write the final answer.

The model never runs code itself. It only requests a tool.

## Requirements
- Windows, macOS or Linux
- Python 3.10 or newer
- Ollama with a tool-capable model, for example:
  `ollama pull qwen2.5:3b` (or `qwen3`)

## Quick start
1. Install and open Ollama, then pull a model.
2. Download this repository and open the folder in a terminal.
3. Create an environment and install packages:
