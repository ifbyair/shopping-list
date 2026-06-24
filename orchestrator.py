"""
orchestrator.py — coordinates agents, now with semantic memory injection.

Change from previous version:
  - retrieve_relevant() called before each LLM call
  - Relevant facts injected into system prompt as context
  - extract_facts() + store_facts() called after each response
"""

import json
import anthropic
from agent import run_agent
from recipe_agent import run_recipe_agent
from memory import retrieve_relevant, extract_facts, store_facts

client = anthropic.Anthropic()

BASE_SYSTEM_PROMPT = """You are a household assistant that coordinates a shopping list
and meal planning.

You have two specialist agents you can delegate to:
- Shopping agent: handles the shopping list (adding items, checking what's needed, etc.)
- Recipe agent: suggests meals based on available ingredients

For any message:
- If it's about the shopping list → delegate to the shopping agent
- If it's about meals, recipes, or "what can I make" → delegate to the recipe agent
- If it involves both → call both

Always delegate — never answer shopping or recipe questions yourself.
Combine the agents' responses into one friendly, coherent reply."""

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


def _extract_text(response_content) -> str:
    """Safely extract plain text from an agent response."""
    if isinstance(response_content, str):
        return response_content
    if isinstance(response_content, list):
        return " ".join(
            block.text for block in response_content
            if hasattr(block, "text")
        )
    return str(response_content)


def _build_system_prompt(sender: str, user_message: str) -> str:
    """Build system prompt with relevant memories injected."""
    facts = retrieve_relevant(sender, user_message)
    if not facts:
        return BASE_SYSTEM_PROMPT

    facts_text = "\n".join(f"- {f}" for f in facts)
    return f"""{BASE_SYSTEM_PROMPT}

--- What you know about this user ---
{facts_text}
-------------------------------------
Use this context naturally when relevant. Don't mention that you have a memory system."""


def run_orchestrator(user_message: str, sender: str, shopping_history: list) -> str:
    """
    Run one turn of the orchestrator loop.
    Retrieves relevant memories before responding,
    extracts new facts after responding.
    """
    # Inject relevant memories into system prompt
    system_prompt = _build_system_prompt(sender, user_message)

    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [orchestrator] delegating to: {block.name}")

                    if block.name == "ask_shopping_agent":
                        result = _extract_text(run_agent(block.input["message"], shopping_history))
                    elif block.name == "ask_recipe_agent":
                        result = _extract_text(run_recipe_agent(block.input["message"]))
                    else:
                        result = f"Unknown agent: {block.name}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            final_text = next(
                (block.text for block in response.content if hasattr(block, "text")), ""
            )

            # Extract and store facts from this exchange
            facts = extract_facts(user_message, final_text)
            if facts:
                store_facts(sender, facts)

            return final_text


if __name__ == "__main__":
    print("🏠 Household Assistant (with semantic memory)")
    print("   Try: 'I hate mushrooms'")
    print("   Then: 'what can I make for dinner?'\n")

    sender = "local-user"
    from storage import load_history, save_history, clear_history

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input or user_input.lower() in ("quit", "exit"):
            break

        if user_input.lower() in ("reset", "forget everything"):
            clear_history(sender)
            print("Memory cleared!\n")
            continue

        history = load_history(sender)
        response = run_orchestrator(user_input, sender, history)
        save_history(sender, history)
        print(f"\nAssistant: {response}\n")
