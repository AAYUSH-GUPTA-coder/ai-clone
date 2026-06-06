"""
Quick diagnostic: lists embedding models available for your Gemini API key.
Usage:  uv run python check_api.py YOUR_GEMINI_API_KEY
"""
import sys
import requests

if len(sys.argv) < 2:
    print("Usage: uv run python check_api.py YOUR_GEMINI_API_KEY")
    sys.exit(1)

key = sys.argv[1]

resp = requests.get(
    "https://generativelanguage.googleapis.com/v1beta/models",
    headers={"x-goog-api-key": key},
    timeout=10,
)
print(f"HTTP {resp.status_code}")
if resp.status_code != 200:
    print(resp.text)
    sys.exit(1)

models = resp.json().get("models", [])
embed_models = [
    m for m in models
    if "embedContent" in m.get("supportedGenerationMethods", [])
    or "batchEmbedContents" in m.get("supportedGenerationMethods", [])
]

print(f"\nEmbedding-capable models ({len(embed_models)} found):")
for m in embed_models:
    print(f"  {m['name']}  —  {m.get('displayName', '')}")

print(f"\nAll models ({len(models)} total):")
for m in models:
    print(f"  {m['name']}")
