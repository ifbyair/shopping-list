"""
whatsapp.py — webhook server, now pointing at the orchestrator.

The only change from before: run_agent() is replaced by run_orchestrator().
Everything else is identical — showing how cleanly multi-agent plugs in.
"""

from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from orchestrator import run_orchestrator
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

    try:
        reply = run_orchestrator(incoming_msg, sender)
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
