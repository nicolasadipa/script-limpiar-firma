"""
list_columns.py — Lista todas las columnas del board de Monday.com.

Útil para identificar el ID exacto de la columna de firmas.
"""

from monday_client import _make_request, MONDAY_BOARD_ID

query = """
query {
    boards(ids: [%s]) {
        columns {
            id
            title
            type
        }
    }
}
""" % MONDAY_BOARD_ID

data = _make_request(query)
board = data["boards"][0]

print("\n" + "=" * 80)
print("COLUMNAS DEL BOARD")
print("=" * 80)

for col in board["columns"]:
    print(
        f"Título: {col['title']:<30} | ID: {col['id']:<20} | "
        f"Tipo: {col['type']:<15}"
    )

print("=" * 80)
