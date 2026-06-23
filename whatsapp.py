"""
whatsapp.py — webhook server that connects WhatsApp (via Twilio) to the shopping agent.
"""

from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from agent import run_agent
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

conversation_histories = {}


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.form.get("Body", "").strip()
    sender       = request.form.get("From", "")

    print(f"[{sender}] {incoming_msg}")

    if not incoming_msg:
        return Response("", status=204)

    if sender not in conversation_histories:
        conversation_histories[sender] = []

    history = conversation_histories[sender]

    try:
        reply = run_agent(incoming_msg, history)
    except Exception as e:
        print(f"Agent error: {e}")
        reply = "Sorry, something went wrong. Please try again."

    resp = MessagingResponse()
    resp.message(reply)
    return Response(str(resp), mimetype="text/xml")


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "conversations": len(conversation_histories)}


if __name__ == "__main__":
    print("🛒 Shopping Agent — WhatsApp webhook running on port 5000")
    print("   Health check: http://localhost:5000/health")
    print("   Webhook URL:  http://localhost:5000/whatsapp")
    app.run(debug=True, port=5000)

