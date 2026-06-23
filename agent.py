"""
agent.py — the agent loop.
"""

import json
import anthropic
from dotenv import load_dotenv
from tools import TOOLS, TOOL_FUNCTIONS

load_dotenv()

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


def _serialize_content(content) -> list:
    """
    Convert Anthropic SDK content blocks (TextBlock, ToolUseBlock, etc.)
    into plain dicts that can be stored in SQLite via json.dumps.
    """
    result = []
    for block in content:
        if block.type == "text":
            result.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            result.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return result


def run_agent(user_message: str, history: list) -> str:
    """
    Run one turn of the agent loop.
    Mutates `history` in place. Returns the assistant's final text response.
    """
    history.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )

        if response.stop_reason == "tool_use":
            # Serialize SDK objects → plain dicts before storing in history
            serialized = _serialize_content(response.content)
            history.append({"role": "assistant", "content": serialized})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [tool call] {block.name}({json.dumps(block.input)})")
                    fn = TOOL_FUNCTIONS[block.name]
                    result = fn(block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            history.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            final_text = next(
                (block.text for block in response.content if hasattr(block, "text")), ""
            )
            history.append({"role": "assistant", "content": final_text})
            return final_text

        else:
            return f"[unexpected stop reason: {response.stop_reason}]"


def main():
    print("🛒 Shopping List Agent")
    print("  Type your message, or 'quit' to exit.\n")

    history = []

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
