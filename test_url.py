"""
test_url.py — Prueba diferentes formas de acceder a la URL del archivo.
"""

import requests

base_url = "https://adipa.monday.com/protected_static/7038859/resources/2405495394/firma%20digital%20RTA.JPG"

urls_to_test = [
    base_url,
    base_url.replace("protected_static", "static"),
    "https://cdn.monday.com/static/7038859/resources/2405495394/firma%20digital%20RTA.JPG",
    "https://adipa-prod-cdn.monday.com/7038859/2405495394/firma%20digital%20RTA.JPG",
]

print("Probando diferentes variantes de URL:\n")

for i, url in enumerate(urls_to_test, 1):
    print(f"{i}. Probando: {url[:70]}...")
    try:
        response = requests.head(
            url,
            timeout=10,
            allow_redirects=True,
        )
        print(f"   Status: {response.status_code}")
        print(f"   URL final: {response.url[:80]}")
        if response.status_code in [200, 302]:
            print(f"   ✓ POTENCIALMENTE FUNCIONA")
    except Exception as e:
        print(f"   Error: {str(e)[:60]}")
    print()
