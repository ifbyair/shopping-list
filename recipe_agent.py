"""
recipe_agent.py — a specialist agent that suggests meals.

It has one tool: ask_shopping_list, which calls the shopping agent
to find out what's currently available. It uses that context to
suggest realistic meals the user can actually make.

This agent has no direct access to storage — it must go through
the shopping agent to get list data. That's intentional: each agent
only knows about its own domain.
"""

import json
import anthropic
from tools import get_list  # reuse the existing shopping tool directly

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a helpful meal planning assistant.

When asked for meal ideas, you first check what items are active on the
shopping list — these are ingredients the user is about to buy or has at home.
Use that context to suggest 2-3 realistic, simple meals.

Be concise and practical. Format suggestions clearly.
If the shopping list has very few items, suggest meals and note what
extra ingredients might be needed."""

# The recipe agent's one tool: ask the shopping agent for the current list
TOOLS = [
    {
        "name": "get_shopping_list",
        "description": (
            "Get the current shopping list to see what ingredients are available. "
            "Call this before suggesting any meals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }
]


def run_recipe_agent(user_message: str) -> str:
    """
    Run the recipe agent for one turn.
    No persistent history — each meal planning request is self-contained.
    """
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [recipe agent] tool call: {block.name}")

                    # The only tool this agent has — get the shopping list
                    result = get_list()

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            return next(
                (block.text for block in response.content if hasattr(block, "text")), ""
            )
