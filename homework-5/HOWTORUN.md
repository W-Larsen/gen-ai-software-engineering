# HOWTORUN — Custom MCP Server (FastMCP)

This guide covers the **custom FastMCP server** in [`custom-mcp-server/`](custom-mcp-server/):
how to install dependencies, run the server, wire it into your MCP client, and
test the `read` tool.

---

## 1. Prerequisites

- **Python 3.12 or 3.13** (recommended). FastMCP depends on `pydantic`, which does
  **not** yet support the Python **3.14 release candidate** — under 3.14rc you get
  `TypeError: _eval_type() got an unexpected keyword argument 'prefer_fwd_module'`.
- Optional but recommended: [`uv`](https://docs.astral.sh/uv/) for creating an
  isolated environment with a pinned Python.

---

## 2. Install dependencies

All commands are run from the `custom-mcp-server/` folder.

### Option A — using `uv` (recommended, pins a stable Python)

```bash
cd custom-mcp-server

# Create an isolated environment with a compatible interpreter
uv venv --python 3.12 .venv

# Install dependencies (fastmcp) into it
uv pip install --python .venv -r requirements.txt
```

> If `uv` is not on your PATH but you have it via pip, replace `uv` with
> `python -m uv` in the commands above.

### Option B — using plain `pip` (requires Python 3.12/3.13 as your `python`)

```bash
cd custom-mcp-server
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
```

`fastmcp` is declared as a dependency in both
[`requirements.txt`](custom-mcp-server/requirements.txt) and
[`pyproject.toml`](custom-mcp-server/pyproject.toml).

---

## 3. Run the server

The server speaks the MCP protocol over **stdio**, so it is normally launched by
your MCP client. To confirm it starts up:

```bash
# Windows
.venv\Scripts\python.exe server.py

# macOS/Linux
.venv/bin/python server.py
```

You should see the FastMCP banner and
`Starting MCP server 'Lorem Ipsum Server' with transport 'stdio'`.
Press `Ctrl+C` to stop (an MCP client manages this lifecycle for you).

---

## 4. Connect the MCP configuration

The repository ships a ready-to-use config at
[`../.mcp.json`](.mcp.json) (homework-5 root). The custom server is registered
under the key **`lorem-ipsum`**:

```json
{
  "mcpServers": {
    "lorem-ipsum": {
      "command": "D:/.../homework-5/custom-mcp-server/.venv/Scripts/python.exe",
      "args": [
        "D:/.../homework-5/custom-mcp-server/server.py"
      ]
    }
  }
}
```

- **`command`** points at the venv's Python (so the correct 3.12 interpreter and
  `fastmcp` are used).
- **`args`** is the absolute path to `server.py`.
- Update both absolute paths to match your machine.

### Registering with Claude Code

Either place `.mcp.json` at the project root (Claude Code auto-discovers it), or
add the server explicitly:

```bash
claude mcp add lorem-ipsum -- "<abs-path>/.venv/Scripts/python.exe" "<abs-path>/server.py"
```

Then run `claude mcp list` — the `lorem-ipsum` server should report as connected.

---

## 5. Use / test the `read` tool

### From Claude

Ask Claude:

- *"Use the lorem-ipsum `read` tool to return 30 words."*
- *"Call `read` with word_count = 10."*
- *"Read the `lorem://ipsum` resource."*

### Standalone smoke test (no client needed)

Run this from `custom-mcp-server/` with the venv's Python:

```bash
.venv/Scripts/python.exe - <<'PY'
import asyncio
from fastmcp import Client
import server

async def main():
    async with Client(server.mcp) as c:
        print("tools:", [t.name for t in await c.list_tools()])
        print("read() default:", (await c.call_tool("read", {})).data)
        print("read(5):", (await c.call_tool("read", {"word_count": 5})).data)
        print("resource:", (await c.read_resource("lorem://ipsum/10"))[0].text)

asyncio.run(main())
PY
```

Expected: `read()` returns 30 words, `read(5)` returns 5 words, and the
`lorem://ipsum/10` resource returns 10 words.

---

## 6. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `_eval_type() ... 'prefer_fwd_module'` | You're on Python 3.14rc. Use the 3.12 venv (Section 2). |
| `ModuleNotFoundError: fastmcp` | Dependencies not installed into the venv — re-run Section 2. |
| Client can't launch server | Check that both paths in `.mcp.json` are absolute and correct. |
