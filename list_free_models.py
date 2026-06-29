#!/usr/bin/env python3
"""List all free models from OpenRouter API"""
import urllib.request, json, os

key = os.environ.get("OPENROUTER_API_KEY", "")

req = urllib.request.Request(
    "https://openrouter.ai/api/v1/models",
    headers={"Authorization": f"Bearer {key}"}
)
resp = urllib.request.urlopen(req, timeout=30)
data = json.loads(resp.read())

free_models = []
for m in data.get("data", []):
    id = m.get("id", "")
    pricing = m.get("pricing", {})
    # Check if it's free (prompt = 0 and completion = 0) or has :free suffix
    is_free = pricing.get("prompt") == 0 and pricing.get("completion") == 0
    has_free_suffix = id.endswith(":free")
    
    if is_free or has_free_suffix:
        name = m.get("name", id)
        context = m.get("context_length", "?")
        description = m.get("description", "")[:100]
        free_models.append({
            "id": id,
            "name": name,
            "context": context,
            "pricing": pricing,
            "description": description
        })

print(f"Total free models: {len(free_models)}")
print("=" * 80)
for m in sorted(free_models, key=lambda x: x["id"]):
    print(f"\nID: {m['id']}")
    print(f"   Name: {m['name']}")
    print(f"   Context: {m['context']}")
    print(f"   Desc: {m['description'][:80]}")
