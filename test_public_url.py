"""
test_public_url.py — Intenta obtener public_url desde Monday.com API.
"""

import json
import requests
from dotenv import load_dotenv
import os

load_dotenv()
token = os.getenv("MONDAY_API_TOKEN")

# Query con public_url (en snake_case)
query = """
query {
    items(ids: ["9509181460"]) {
        id
        name
        assets {
            id
            name
            url
            public_url
        }
    }
}
"""

headers = {
    "Authorization": token,
    "Content-Type": "application/json",
}

payload = {"query": query}

print("Consultando assets con public_url...\n")

response = requests.post(
    "https://api.monday.com/v2",
    json=payload,
    headers=headers,
)

data = response.json()
print(json.dumps(data, indent=2))
