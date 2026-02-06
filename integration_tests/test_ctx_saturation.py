"""Test simple de saturation du contexte llama.cpp sur DGX Spark."""

import requests

HOST = "gx10-957b"
PORT = 8002
BASE = f"http://{HOST}:{PORT}"

# 1. Récupérer la config actuelle du serveur
print("=== Config serveur ===")
settings = requests.get(f"{BASE}/props", timeout=10).json().get("default_generation_settings", {})
for key in ["n_ctx", "n_predict", "temperature", "top_k", "top_p"]:
    print(f"  {key}: {settings.get(key, '(absent)')}")
print()

# 2. Envoyer un prompt long pour tester la saturation
# On vise ~2000 tokens de prompt pour laisser de la place à l'output
# Le modèle Qwen3-30B-A3B supporte jusqu'à 32768 tokens
chunk = (
    "Generate a valid JSON object describing a comprehensive research report. "
    "Include title, executive_summary (at least 1000 words), methodology, "
    "findings with 10 detailed sections, conclusions, and follow_up_questions. "
)
prompt = chunk * 50  # ~2000-3000 tokens de prompt

print("=== Test saturation ===")
response = requests.post(
    f"{BASE}/completion",
    json={"prompt": prompt},
    timeout=300,
)
data = response.json()

output = data.pop("content", "")
print("=== Réponse serveur (sans contenu) ===")
for k, v in data.items():
    print(f"  {k}: {v}")
print(f"  output length (chars): {len(output)}")
print()

# 3. Diagnostic
stop_type = data.get("stop_type", "?")
if stop_type == "limit":
    print(">>> TRONCATURE : le modèle a été coupé par une limite")
elif stop_type == "eos":
    print(">>> OK : le modèle s'est arrêté naturellement (eos)")
else:
    print(f">>> Stop type: {stop_type}")

print()
print("--- Derniers 300 caractères de l'output ---")
print(output[-300:])
