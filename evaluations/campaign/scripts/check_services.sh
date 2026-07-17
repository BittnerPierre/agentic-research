#!/bin/bash
# Pré-vol de campagne : vérifie chaque dépendance et dit ce qui manque.
# Usage: check_services.sh [--spark]   (--spark : exige aussi vLLM spark1:8000)
# Sort avec code 1 si un service requis manque. NE DÉMARRE RIEN :
# le démarrage/redémarrage des services est du ressort de l'utilisateur
# (règle actée : proposer la commande, ne pas l'exécuter).
set -u
NEED_SPARK=${1:-}
OK=0

check() { # label, ok(0/1), détail, remède
  if [ "$2" = "0" ]; then echo "✓ $1 — $3"; else echo "✗ $1 — $3"; echo "    remède : $4"; OK=1; fi
}

# ChromaDB (localhost:8000)
if curl -s --max-time 3 http://localhost:8000/api/v2/heartbeat >/dev/null 2>&1; then
  check "ChromaDB (localhost:8000)" 0 "up" ""
else
  check "ChromaDB (localhost:8000)" 1 "injoignable" "démarrer le conteneur/service Chroma"
fi

# DataPrep MCP (localhost:8001) — noter la config avec laquelle il tourne si possible
if lsof -nP -iTCP:8001 -sTCP:LISTEN >/dev/null 2>&1; then
  check "DataPrep MCP (localhost:8001)" 0 "up (vérifier que sa config d'embeddings correspond à la campagne)" ""
else
  check "DataPrep MCP (localhost:8001)" 1 "aucun listener" \
    "uv run dataprep_server --config <config-de-campagne>  (à lancer par l'utilisateur)"
fi

# Embeddings (spark1:8003)
EMB=$(curl -s --max-time 4 http://spark1:8003/v1/models 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null)
if [ -n "${EMB:-}" ]; then
  check "Embeddings (spark1:8003)" 0 "sert: $EMB" ""
else
  check "Embeddings (spark1:8003)" 1 "injoignable" "démarrer llama.cpp embeddings sur le Spark (utilisateur)"
fi

# vLLM (spark1:8000) — requis seulement pour les modèles Spark
VLLM=$(curl -s --max-time 4 http://spark1:8000/v1/models 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null)
if [ -n "${VLLM:-}" ]; then
  check "vLLM (spark1:8000)" 0 "sert: $VLLM" ""
elif [ "$NEED_SPARK" = "--spark" ]; then
  check "vLLM (spark1:8000)" 1 "injoignable (requis pour un modèle Spark)" "swap/démarrage vLLM par l'utilisateur"
else
  echo "· vLLM (spark1:8000) — injoignable (OK si campagne cloud uniquement)"
fi

# Clé API (juge + modèles cloud)
if [ -n "${OPENAI_API_KEY:-}" ] || grep -q "OPENAI_API_KEY" .env 2>/dev/null; then
  check "OPENAI_API_KEY" 0 "présente (env ou .env)" ""
else
  check "OPENAI_API_KEY" 1 "absente" "exporter la clé ou la mettre dans .env (le juge en dépend)"
fi

exit $OK
