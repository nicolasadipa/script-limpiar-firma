"""
debug_file.py — Inspecciona la estructura completa del archivo en Monday.com.
"""

import json
from monday_client import _make_request, MONDAY_BOARD_ID

item_id = "9509181460"  # TS. Rocío Troncoso
file_column_id = "archivo9"  # Columna Firma

print("\n" + "=" * 80)
print("QUERY 1: Usando files()")
print("=" * 80)

query1 = """
query {
    items(ids: ["%s"]) {
        id
        name
        files(ids: ["%s"]) {
            id
            name
            size
            url
            publicUrl
            assetId
            fileType
            isImage
        }
    }
}
""" % (item_id, file_column_id)

try:
    data = _make_request(query1)
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 80)
print("QUERY 2: Usando column_values()")
print("=" * 80)

query2 = """
query {
    items(ids: ["%s"]) {
        id
        name
        column_values(ids: ["%s"]) {
            id
            value
            text
            type
        }
    }
}
""" % (item_id, file_column_id)

try:
    data = _make_request(query2)
    print(json.dumps(data, indent=2))
    if data.get("items"):
        col_val = data["items"][0].get("column_values", [{}])[0].get("value")
        if col_val:
            print("\nValor parseado como JSON:")
            parsed = json.loads(col_val)
            print(json.dumps(parsed, indent=2))
except Exception as e:
    print(f"Error: {e}")
