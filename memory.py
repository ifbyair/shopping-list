"""
memory.py — long-term semantic memory using Voyage AI + ChromaDB.
"""

import os
import json
import anthropic
import voyageai
import chromadb
from dotenv import load_dotenv

load_dotenv()

claude = anthropic.Anthropic()
voyage = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))

CHROMA_PATH = os.getenv("CHROMA_PATH", "/app/data/chroma")

_chroma_client = None

def _get_chroma():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _chroma_client


def _get_collection(sender: str):
    safe_name = "mem_" + sender.replace(":", "_").replace("+", "").replace("-", "_")
    return _get_chroma().get_or_create_collection(safe_name)


# ── Fact extraction ───────────────────────────────────────────────────────────

EXTRACT_PROMPT = """You are a memory extraction assistant.
Given a conversation exchange, extract any facts worth remembering long-term about the user.

Focus on:
- Dietary restrictions and preferences ("User is lactose intolerant", "User is vegetarian")
- Food likes and dislikes ("User dislikes mushrooms", "User loves spicy food")
- Habits and routines ("User shops on Saturdays")
- Household info ("User has two kids", "User cooks for a family of four")
- Any other stable personal facts

Do NOT extract:
- Transient shopping list changes ("User added milk")
- Generic assistant responses

IMPORTANT: Extract facts from BOTH what the user said AND the context of the conversation.
If the user says "I am lactose intolerant", extract "User is lactose intolerant" even if
the assistant's reply was just a shopping list update.

Respond with a JSON array of fact strings. If no facts worth remembering, return [].
Example: ["User is lactose intolerant", "User prefers oat milk over regular milk"]

Respond with ONLY the JSON array, no other text."""


def extract_facts(user_message: str, agent_reply: str) -> list[str]:
    """Extract memorable facts from a conversation exchange."""
    try:
        response = claude.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            system=EXTRACT_PROMPT,
            messages=[{
                "role": "user",
                "content": f"User said: {user_message}\nAssistant replied: {agent_reply}"
            }]
        )
        text = response.content[0].text.strip()
        facts = json.loads(text)
        return facts if isinstance(facts, list) else []
    except Exception as e:
        print(f"  [memory] fact extraction failed: {e}")
        return []


# ── Storage and retrieval ─────────────────────────────────────────────────────

def store_facts(sender: str, facts: list[str]) -> None:
    """Embed facts via Voyage AI and store in ChromaDB."""
    if not facts:
        return
    try:
        collection = _get_collection(sender)
        result = voyage.embed(facts, model="voyage-3", input_type="document")
        embeddings = result.embeddings

        import hashlib
        ids = [hashlib.md5(f.encode()).hexdigest() for f in facts]

        collection.upsert(ids=ids, embeddings=embeddings, documents=facts)
        print(f"  [memory] stored {len(facts)} fact(s): {facts}")
    except Exception as e:
        print(f"  [memory] storage failed: {e}")


def retrieve_relevant(sender: str, query: str, n_results: int = 5) -> list[str]:
    """Find facts semantically relevant to the current query."""
    try:
        collection = _get_collection(sender)
        if collection.count() == 0:
            return []
        result = voyage.embed([query], model="voyage-3", input_type="query")
        query_embedding = result.embeddings[0]
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, collection.count()),
        )
        return results["documents"][0] if results["documents"] else []
    except Exception as e:
        print(f"  [memory] retrieval failed: {e}")
        return []


def get_all_facts(sender: str) -> list[str]:
    """Return all stored facts for a sender."""
    try:
        collection = _get_collection(sender)
        if collection.count() == 0:
            return []
        results = collection.get()
        return results["documents"]
    except Exception as e:
        print(f"  [memory] get_all failed: {e}")
        return []


def clear_memories(sender: str) -> None:
    """Delete all memories for a sender."""
    try:
        safe_name = "mem_" + sender.replace(":", "_").replace("+", "").replace("-", "_")
        _get_chroma().delete_collection(safe_name)
        print(f"  [memory] cleared all memories for {sender}")
    except Exception as e:
        print(f"  [memory] clear failed: {e}")
