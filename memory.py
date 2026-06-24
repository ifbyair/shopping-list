"""
memory.py — long-term semantic memory using Voyage AI + ChromaDB.

Two responsibilities:
  1. Extract facts from conversations (via Claude)
  2. Store and retrieve them semantically (via Voyage AI + ChromaDB)

Flow:
  After each message:
    extract_facts(user_msg, agent_reply) → ["User dislikes mushrooms", ...]
    store_facts(sender, facts)           → embedded + stored in ChromaDB

  Before each message:
    retrieve_relevant(sender, user_msg)  → ["User dislikes mushrooms"]
    injected into orchestrator system prompt as context
"""

import os
import json
import anthropic
import voyageai
import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv

load_dotenv()

# ── Clients ───────────────────────────────────────────────────────────────────

claude  = anthropic.Anthropic()
voyage  = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))

# ChromaDB persisted to the Railway volume (same as SQLite and JSON)
CHROMA_PATH = os.getenv("CHROMA_PATH", "/app/data/chroma")

_chroma_client = None

def _get_chroma() -> chromadb.Client:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _chroma_client


def _get_collection(sender: str) -> chromadb.Collection:
    """Each sender gets their own ChromaDB collection."""
    # Collection names must be alphanumeric + underscores
    safe_name = "mem_" + sender.replace(":", "_").replace("+", "").replace("-", "_")
    return _get_chroma().get_or_create_collection(safe_name)


# ── Fact extraction ───────────────────────────────────────────────────────────

EXTRACT_PROMPT = """You are a memory extraction assistant. 
Given a conversation exchange, extract any facts worth remembering long-term about the user.

Focus on:
- Preferences and dislikes ("User doesn't eat meat", "User prefers oat milk")
- Habits and routines ("User shops on Saturdays", "User buys coffee weekly")  
- Household info ("User has two kids", "User is vegetarian")
- Any other stable personal facts

Do NOT extract:
- Transient shopping list changes ("User added milk" — that's in the list already)
- Generic assistant responses
- Facts that are already obvious

Respond with a JSON array of fact strings. If no facts worth remembering, return [].
Example: ["User prefers oat milk over regular milk", "User shops on weekends"]

Respond with ONLY the JSON array, no other text."""


def extract_facts(user_message: str, agent_reply: str) -> list[str]:
    """Use Claude to extract memorable facts from a conversation exchange."""
    try:
        response = claude.messages.create(
            model="claude-haiku-4-5",  # fast + cheap for extraction
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

        # Embed all facts in one API call
        result = voyage.embed(facts, model="voyage-3", input_type="document")
        embeddings = result.embeddings

        # Use fact text as ID (deduplicates identical facts automatically)
        import hashlib
        ids = [hashlib.md5(f.encode()).hexdigest() for f in facts]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=facts,
        )
        print(f"  [memory] stored {len(facts)} fact(s) for {sender}")

    except Exception as e:
        print(f"  [memory] storage failed: {e}")


def retrieve_relevant(sender: str, query: str, n_results: int = 5) -> list[str]:
    """Find facts semantically relevant to the current query."""
    try:
        collection = _get_collection(sender)

        # Check if collection has any facts
        if collection.count() == 0:
            return []

        # Embed the query
        result = voyage.embed([query], model="voyage-3", input_type="query")
        query_embedding = result.embeddings[0]

        # Search for similar facts
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, collection.count()),
        )

        return results["documents"][0] if results["documents"] else []

    except Exception as e:
        print(f"  [memory] retrieval failed: {e}")
        return []


def get_all_facts(sender: str) -> list[str]:
    """Return all stored facts for a sender (for the 'memories' command)."""
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
