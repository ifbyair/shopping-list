"""
storage.py — handles reading and writing the shopping list to disk.
Nothing AI-related here, just plain data management.
"""

import json
import os

DATA_FILE = "shopping_list.json"

DEFAULT_DATA = {
    "items": [
        {"name": "toilet paper", "status": "inactive", "staple": True},
        {"name": "dish soap",    "status": "inactive", "staple": True},
        {"name": "olive oil",    "status": "inactive", "staple": True},
        {"name": "coffee",       "status": "inactive", "staple": True},
    ]
}


def load() -> dict:
    if not os.path.exists(DATA_FILE):
        save(DEFAULT_DATA)
        return DEFAULT_DATA
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
