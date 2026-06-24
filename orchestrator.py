"""
orchestrator.py — coordinates agents with memory injected into all specialists.
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

Routing rules:
- Shopping list requests (add, remove, activate, check, buy) → ask_shopping_agent
- ANY mention of meals, food suggestions, cooking, dinner, lunch, breakfast,
  recipes, "what can I make", "what can I cook", "suggest", "what's for dinner",
  "meal ideas" → ask_recipe_agent
- Requests involving both → call both

Always delegate — never answer shopping or recipe questions yourself.
Combine the agents' responses into one friendly, coherent reply."""

TOOLS = [
    {
        "name": "ask_shopping_agent",
        "description": (
            "Delegate to the shopping list agent. Use for adding, removing, activating, "
            "checking, or managing items on the shopping list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message for the shopping agent."},
                "user_context": {"type": "string", "description": "Relevant user facts/preferences to be aware of."},
            },
            "required": ["message"],
        },
    },
    {
        "name": "ask_recipe_agent",
        "description": (
            "Delegate to the meal planning agent. Use for ANY request about meals, recipes, "
            "cooking suggestions, dinner ideas, or what the user can make or eat."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message for the recipe agent."},
                "user_context": {"type": "string", "description": "Relevant user facts/preferences to be aware of."},
            },
            "required": ["message"],
        },
    },
]


def _extract_text(response_content) -> str:
    if isinstance(response_content, str):
        return response_content
    if isinstance(response_content, list):
        return " ".join(
            block.text for block in response_content if hasattr(block, "text")
        )
    return str(response_content)


def _build_system_prompt(sender: str, user_message: str) -> str:
    facts = retrieve_relevant(sender, user_message)
    if not facts:
        return BASE_SYSTEM_PROMPT
    facts_text = "\n".join(f"- {f}" for f in facts)
    return f"""{BASE_SYSTEM_PROMPT}

--- What you know about this user ---
{facts_text}
-------------------------------------
Use this context when routing and when passing user_context to agents.
Do not mention that you have a memory system."""


def _format_context(facts: list[str]) -> str:
    """Format facts as a context string to pass to specialist agents."""
    if not facts:
        return ""
    return "User context:\n" + "\n".join(f"- {f}" for f in facts)


def run_orchestrator(user_message: str, sender: str, shopping_history: list) -> str:
    """Run one turn of the orchestrator loop with memory injection."""
    # Get relevant memories once — used both in system prompt and passed to agents
    relevant_facts = retrieve_relevant(sender, user_message)
    user_context   = _format_context(relevant_facts)
    system_prompt  = _build_system_prompt(sender, user_message)

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

                    # Pass user context + message to specialist agents
                    agent_message = block.input["message"]
                    if user_context:
                        agent_message = f"{user_context}\n\n{agent_message}"

                    if block.name == "ask_shopping_agent":
                        result = _extract_text(run_agent(agent_message, shopping_history))
                    elif block.name == "ask_recipe_agent":
                        result = _extract_text(run_recipe_agent(agent_message))
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
    print("   Try: 'I am lactose intolerant'")
    print("   Then: 'add milk to my list'")
    print("   Then: 'suggest a meal for dinner tonight'\n")

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
            print("History cleared!\n")
            continue

        history = load_history(sender)
        response = run_orchestrator(user_input, sender, history)
        save_history(sender, history)
        print(f"\nAssistant: {response}\n")
