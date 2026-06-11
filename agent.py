"""
agent.py — the agent loop. This is the core of the whole thing.

The flow per user message:
  1. Send message + tools to Claude
  2. If Claude wants to call a tool → run it, send result back
  3. Repeat until Claude gives a final text response
  4. Print response, wait for next user message

Conversation history is kept in memory for the session,
so the agent remembers context within a conversation.
"""

import json
import anthropic
from tools import TOOLS, TOOL_FUNCTIONS

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a helpful shopping list assistant.

You help the user manage their shopping list. The list has two kinds of items:
- Staples: things they buy regularly (toilet paper, coffee, etc.)
- One-off items: things needed once

When the user says they "ran out" of something or "need" something, activate it.
When they say they "bought" it or "got" it, deactivate it.
If it's a new recurring item, add it as a staple.

Always confirm what you did in a short, friendly message. 
When showing the list, format it clearly."""

def run_agent(user_message: str, history: list) -> str:
    """
    Run one turn of the agent loop.
    Mutates `history` in place (appends user message and assistant response).
    Returns the assistant's final text response.
    """

    # Add user message to history
    history.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )

        # ── Case 1: Claude wants to call one or more tools ──────────────────
        if response.stop_reason == "tool_use":

            # Append Claude's response (which contains tool call requests) to history
            history.append({"role": "assistant", "content": response.content})

            # Process every tool call in this response (can be multiple)
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [tool call] {block.name}({json.dumps(block.input)})")

                    # Actually run the tool
                    fn = TOOL_FUNCTIONS[block.name]
                    result = fn(block.input)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            # Send tool results back to Claude
            history.append({"role": "user", "content": tool_results})

            # Loop again — Claude will now produce either another tool call or a final answer

        # ── Case 2: Claude is done, final text response ──────────────────────
        elif response.stop_reason == "end_turn":
            final_text = next(
                (block.text for block in response.content if hasattr(block, "text")), ""
            )
            # Append assistant's final response to history
            history.append({"role": "assistant", "content": final_text})
            return final_text

        else:
            return f"[unexpected stop reason: {response.stop_reason}]"


def main():
    print("🛒 Shopping List Agent")
    print("  Type your message, or 'quit' to exit.\n")

    history = []  # Persists within the session

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Bye!")
            break

        response = run_agent(user_input, history)
        print(f"\nAgent: {response}\n")


if __name__ == "__main__":
    main()
