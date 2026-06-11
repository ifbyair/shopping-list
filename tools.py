"""
tools.py — defines what the agent CAN DO.

Two things per tool:
  1. A Python function that actually does the work
  2. A JSON schema that tells the LLM what the tool is and how to call it

The LLM never runs Python — it just emits a tool name + arguments,
and our agent loop calls the matching Python function.
"""

import storage


# ── Python functions ────────────────────────────────────────────────────────

def get_list() -> dict:
    """Return active items and all known staples."""
    data = storage.load()
    active  = [i["name"] for i in data["items"] if i["status"] == "active"]
    staples = [i["name"] for i in data["items"] if i["staple"]]
    inactive_staples = [i["name"] for i in data["items"] if i["staple"] and i["status"] == "inactive"]
    return {
        "active_items": active,
        "staples": staples,
        "inactive_staples": inactive_staples,
    }


def add_item(name: str, staple: bool = False) -> dict:
    """Add a new item to the list and immediately mark it active."""
    data = storage.load()
    name = name.lower().strip()

    # Check if it already exists
    for item in data["items"]:
        if item["name"] == name:
            item["status"] = "active"
            item["staple"] = item["staple"] or staple
            storage.save(data)
            return {"ok": True, "message": f"'{name}' already existed — marked as active."}

    data["items"].append({"name": name, "status": "active", "staple": staple})
    storage.save(data)
    return {"ok": True, "message": f"'{name}' added to your list."}


def activate_item(name: str) -> dict:
    """Mark an existing item as needed (e.g. 'I ran out of X')."""
    data = storage.load()
    name = name.lower().strip()

    for item in data["items"]:
        if item["name"] == name:
            item["status"] = "active"
            storage.save(data)
            return {"ok": True, "message": f"'{name}' is now on your list."}

    return {"ok": False, "message": f"'{name}' not found. Use add_item to add it first."}


def deactivate_item(name: str) -> dict:
    """Mark an item as done / purchased."""
    data = storage.load()
    name = name.lower().strip()

    for item in data["items"]:
        if item["name"] == name:
            item["status"] = "inactive"
            storage.save(data)
            return {"ok": True, "message": f"'{name}' marked as done."}

    return {"ok": False, "message": f"'{name}' not found."}


# ── JSON schemas (what the LLM sees) ────────────────────────────────────────
# This is the "menu" of tools you hand to the API.
# The LLM reads these descriptions to decide which tool to call and with what.

TOOLS = [
    {
        "name": "get_list",
        "description": (
            "Get the current shopping list. Returns active items (things to buy now) "
            "and all known staples (recurring items). Call this when the user asks "
            "what's on the list or what they need to buy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "add_item",
        "description": (
            "Add a new item to the shopping list and mark it as active. "
            "Use staple=true if the user says they always buy this or it's a recurring item."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name":   {"type": "string", "description": "Name of the item, lowercase."},
                "staple": {"type": "boolean", "description": "True if this is a recurring/staple item."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "activate_item",
        "description": (
            "Mark an existing item as needed. Use this when the user says they ran out "
            "of something, or want to add a known item back to their active list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the item to activate."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "deactivate_item",
        "description": (
            "Mark an item as purchased / no longer needed. Use when the user says "
            "they bought something or it's done."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the item to mark as done."},
            },
            "required": ["name"],
        },
    },
]


# ── Dispatcher ───────────────────────────────────────────────────────────────
# Maps tool names to functions so the agent loop can call them dynamically.

TOOL_FUNCTIONS = {
    "get_list":        lambda args: get_list(),
    "add_item":        lambda args: add_item(args["name"], args.get("staple", False)),
    "activate_item":   lambda args: activate_item(args["name"]),
    "deactivate_item": lambda args: deactivate_item(args["name"]),
}
