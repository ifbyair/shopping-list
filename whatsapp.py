"""
whatsapp.py — webhook server with persistent conversation history.

The only meaningful change from the previous version:
  - conversation_histories dict  →  load_history() / save_history() from SQLite
  - Everything else is identical
"""

from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from orchestrator import run_orchestrator
from storage import load_history, save_history, clear_history
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.form.get("Body", "").strip()
    sender       = request.form.get("From", "")

    print(f"[{sender}] {incoming_msg}")

    if not incoming_msg:
        return Response("", status=204)

    # Special command: let user reset their own history
    if incoming_msg.lower() in ("reset", "forget everything"):
        clear_history(sender)
        resp = MessagingResponse()
        resp.message("Memory cleared! Starting fresh.")
        return Response(str(resp), mimetype="text/xml")

    # Load history from DB, run agent, save history back
    history = load_history(sender)

    try:
        reply = run_orchestrator(incoming_msg, sender, history)
        save_history(sender, history)  # history mutated in place by run_orchestrator
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
    app.run(debug=True, port=5000)
