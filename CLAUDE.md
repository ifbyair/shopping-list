# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A command-line shopping-list assistant: a minimal example of the Anthropic tool-use agent loop. The user chats in natural language ("I ran out of coffee"), Claude decides which tool to call, and the tools mutate a JSON file on disk.

## Commands

```bash
# Set up the virtualenv (lives in .shopping/, gitignored)
python3 -m venv .shopping
source .shopping/bin/activate
pip install -r requirements.txt

# The Anthropic SDK reads the API key from the environment
export ANTHROPIC_API_KEY=sk-...

# Run the interactive agent
python agent.py
```

There are no tests, linters, or build steps configured.

## Architecture

Three modules form a clean dependency chain: `agent.py` → `tools.py` → `storage.py`.

- **`agent.py`** — the agent loop. `run_agent()` sends the conversation + tool schemas to Claude, and loops: while `stop_reason == "tool_use"` it executes each tool block, appends the `tool_result` back into `history`, and re-calls the API; on `end_turn` it returns the final text. `history` is a plain list mutated in place and held only in memory, so context survives within a session but is lost on exit. The `SYSTEM_PROMPT` encodes the product behavior (staples vs. one-off items, when to activate/deactivate).

- **`tools.py`** — the tool layer, structured as three parallel pieces that must stay in sync when adding a tool:
  1. a Python function that does the work,
  2. an entry in the `TOOLS` list (the JSON schema Claude sees), and
  3. an entry in the `TOOL_FUNCTIONS` dispatch dict (maps tool name → a lambda that unpacks `args` and calls the function).
  Tool functions take a parsed args dict, return a JSON-serializable dict, and the agent loop `json.dumps`es the return value into the `tool_result`.

- **`storage.py`** — persistence. The entire list is a single JSON file (`shopping_list.json`, gitignored) with one `items` array. Each item has `name` (lowercased), `status` (`active`/`inactive`), and `staple` (bool). There is no DB; every tool call does a full `load()` → mutate → `save()`. If the file is missing, `load()` seeds it with `DEFAULT_DATA`.

## Data model conventions

- Item names are always lowercased/stripped before lookup or insert — preserve this when adding item-handling code, since lookups are exact string matches.
- "active" means *currently needed to buy*; "staple" means *a recurring item* (independent flags — a staple is usually inactive until you run out).
