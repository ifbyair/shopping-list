"""
whatsapp.py — webhook server with persistent history and semantic memory.
"""

from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from orchestrator import run_orchestrator
from storage import load_history, save_history, clear_history
from memory import get_all_facts, clear_memories
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ── Special commands ──────────────────────────────────────────────────────────
RESET_COMMANDS    = {"reset", "forget everything"}
HISTORY_COMMANDS  = {"history", "show history", "my history", "show my history"}
MEMORIES_COMMANDS = {"memories", "what do you know about me", "my memories"}
HELP_COMMANDS     = {"user help", "usage", "commands", "help me"}

HELP_TEXT = """🏠 *Household Assistant — Available Commands*

*Shopping list:*
  "I ran out of coffee" — activates an item
  "Add oat milk" — adds a new item
  "I bought toilet paper" — marks as done
  "Show my list" — shows active items

*Meal planning:*
  "What can I make for dinner?" — suggests meals
  "What can I cook with what I have?" — same

*System commands:*
  `history` — show conversation history
  `memories` — show what I've learned about you
  `reset` — clear history and memories
  `user help` — show this message

You can also just talk naturally — the assistant understands context! 💬"""


def _format_history(history: list) -> str:
    if not history:
        return "No conversation history yet."

    lines = ["🗒️ *Conversation history:*\n"]
    for msg in history:
        role    = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = " ".join(
                block["text"] for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            continue

        if not text.strip():
            continue

        prefix = "👤" if role == "user" else "🤖"
        lines.append(f"{prefix} {text.strip()}")

    return "\n".join(lines)


def _format_memories(facts: list) -> str:
    if not facts:
        return "I don't have any long-term memories about you yet. Just keep chatting!"
    lines = ["🧠 *What I know about you:*\n"]
    for fact in facts:
        lines.append(f"• {fact}")
    return "\n".join(lines)


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.form.get("Body", "").strip()
    sender       = request.form.get("From", "")

    print(f"[{sender}] {incoming_msg}")

    if not incoming_msg:
        return Response("", status=204)

    msg_lower = incoming_msg.lower()
    reply     = None

    # ── Special commands ──────────────────────────────────────────────────────
    if msg_lower in RESET_COMMANDS:
        clear_history(sender)
        clear_memories(sender)
        reply = "Memory cleared! Starting completely fresh. 🧹"

    elif msg_lower in HISTORY_COMMANDS:
        history = load_history(sender)
        reply = _format_history(history)

    elif msg_lower in MEMORIES_COMMANDS:
        facts = get_all_facts(sender)
        reply = _format_memories(facts)

    elif msg_lower in HELP_COMMANDS:
        reply = HELP_TEXT

    # ── Normal message → orchestrator ─────────────────────────────────────────
    else:
        history = load_history(sender)
        try:
            reply = run_orchestrator(incoming_msg, sender, history)
            save_history(sender, history)
        except Exception as e:
            print(f"Orchestrator error: {e}")
            reply = "Sorry, something went wrong. Please try again."

    resp = MessagingResponse()
    resp.message(reply)
    return Response(str(resp), mimetype="text/xml")


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    print("🏠 Household Assistant — WhatsApp webhook running on port 5000")
    print("   Special commands: 'user help', 'history', 'memories', 'reset'")
    app.run(debug=True, port=5000)
