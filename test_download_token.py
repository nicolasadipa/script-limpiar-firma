"""
test_download_token.py — Intenta obtener un token de descarga desde Monday.com API.
"""

import json
import requests
from dotenv import load_dotenv
import os

load_dotenv()
token = os.getenv("MONDAY_API_TOKEN")

# Intentar obtener información del asset incluyendo downloadUrl
query = """
query {
    items(ids: ["9509181460"]) {
        id
        name
        column_values(ids: ["archivo9"]) {
            id
            type
            value
        }
    }
}
"""

headers = {
    "Authorization": token,
    "Content-Type": "application/json",
}

payload = {"query": query}

print("Consultando API de Monday para obtener detalles del asset...\n")

response = requests.post(
    "https://api.monday.com/v2",
    json=payload,
    headers=headers,
)

data = response.json()
print(json.dumps(data, indent=2))

# Extraer el valor
if data.get("data", {}).get("items"):
    col_val = data["data"]["items"][0]["column_values"][0].get("value")
    if col_val:
        parsed = json.loads(col_val)
        print("\n" + "="*80)
        print("JSON de archivos:")
        print(json.dumps(parsed, indent=2))

# Intentar query alternativa con campos adicionales
print("\n" + "="*80)
print("Intentando query con downloadUrl field...\n")

query2 = """
query {
    items(ids: ["9509181460"]) {
        assets(ids: ["archivo9"]) {
            id
            name
            url
            publicUrl
            downloadUrl
        }
    }
}
"""

payload2 = {"query": query2}
response2 = requests.post(
    "https://api.monday.com/v2",
    json=payload2,
    headers=headers,
)

data2 = response2.json()
print(json.dumps(data2, indent=2))
