"""
orchestrator.py — coordinates the shopping and recipe agents.

This is the entry point for all user messages (replaces direct calls to agent.py).
The orchestrator decides which specialist agent(s) to invoke based on intent.

Key concept: the orchestrator's "tools" are other agents, not Python functions.
When it calls "ask_shopping_agent" or "ask_recipe_agent", those are full
agent loops running underneath — not simple function calls.
"""

from dotenv import load_dotenv

load_dotenv()

import json
import anthropic
from agent import run_agent
from recipe_agent import run_recipe_agent

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a household assistant that coordinates a shopping list
and meal planning.

You have two specialist agents you can delegate to:
- Shopping agent: handles the shopping list (adding items, checking what's needed, etc.)
- Recipe agent: suggests meals based on available ingredients

For any message:
- If it's about the shopping list → delegate to the shopping agent
- If it's about meals, recipes, or "what can I make" → delegate to the recipe agent
- If it involves both (e.g. "what can I make and what do I still need to buy?") → call both

Always delegate — never answer shopping or recipe questions yourself.
Combine the agents' responses into one friendly, coherent reply."""

# The orchestrator's tools are the other agents
TOOLS = [
    {
        "name": "ask_shopping_agent",
        "description": (
            "Delegate a message to the shopping list agent. Use for anything related to "
            "the shopping list: adding items, checking what's needed, marking things bought, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message or question to send to the shopping agent."
                }
            },
            "required": ["message"],
        },
    },
    {
        "name": "ask_recipe_agent",
        "description": (
            "Delegate a message to the recipe/meal planning agent. Use when the user "
            "asks about meals, recipes, or what they can cook."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message or question to send to the recipe agent."
                }
            },
            "required": ["message"],
        },
    },
]

# Each sender gets their own shopping history (passed through to shopping agent)
shopping_histories = {}


def run_orchestrator(user_message: str, sender: str) -> str:
    """
    Run one turn of the orchestrator loop.
    Maintains per-sender shopping history; recipe agent is stateless.
    """
    if sender not in shopping_histories:
        shopping_histories[sender] = []

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
                    print(f"  [orchestrator] delegating to: {block.name}({json.dumps(block.input)})")

                    if block.name == "ask_shopping_agent":
                        # Run the full shopping agent loop
                        result = run_agent(
                            block.input["message"],
                            shopping_histories[sender]
                        )
                    elif block.name == "ask_recipe_agent":
                        # Run the full recipe agent loop
                        result = run_recipe_agent(block.input["message"])
                    else:
                        result = f"Unknown agent: {block.name}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,  # agent responses are already strings
                    })

            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            return next(
                (block.text for block in response.content if hasattr(block, "text")), ""
            )


if __name__ == "__main__":
    print("🏠 Household Assistant (multi-agent)")
    print("   Try: 'what can I make for dinner?'")
    print("   Or:  'I ran out of coffee'")
    print("   Or:  'what can I cook and what do I still need to buy?'\n")

    sender = "local-user"
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input or user_input.lower() in ("quit", "exit"):
            break

        response = run_orchestrator(user_input, sender)
        print(f"\nAssistant: {response}\n")
