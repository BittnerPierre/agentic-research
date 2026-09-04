#!/bin/bash
# Pré-vol de campagne : vérifie chaque dépendance et dit ce qui manque.
# Usage: check_services.sh [--spark] [--config <config.yaml>]
#   --spark  : exige aussi vLLM spark1:8000
#   --config : vérifie la CONFORMITÉ (revue Codex #6) — l'embedding servi et le
#              modèle vLLM doivent correspondre à la config de campagne, pas
#              seulement répondre.
# Sort avec code 1 si un service requis manque. NE DÉMARRE RIEN :
# le démarrage/redémarrage des services est du ressort de l'utilisateur
# (règle actée : proposer la commande, ne pas l'exécuter).
set -u
NEED_SPARK=""
CFG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --spark) NEED_SPARK="--spark" ;;
    --config) shift; CFG="${1:-}" ;;
  esac
  shift
done
OK=0
# Coupe à la PREMIÈRE occurrence « clé: » (un sed glouton amputait les URLs à leur dernier deux-points).
cfg_get() { grep -E "^[[:space:]]*$1:" "$CFG" 2>/dev/null | head -1 | sed 's/^[^:]*:[[:space:]]*//; s/"//g'; }

check() { # label, ok(0/1), détail, remède
  if [ "$2" = "0" ]; then echo "✓ $1 — $3"; else echo "✗ $1 — $3"; echo "    remède : $4"; OK=1; fi
}

# ChromaDB (localhost:8000)
if curl -s --max-time 3 http://localhost:8000/api/v2/heartbeat >/dev/null 2>&1; then
  check "ChromaDB (localhost:8000)" 0 "up" ""
else
  check "ChromaDB (localhost:8000)" 1 "injoignable" "démarrer le conteneur/service Chroma"
fi

# DataPrep MCP (localhost:8001) — conformité de config en BEST EFFORT :
# quand le processus est local, sa ligne de commande révèle son --config ; on
# compare alors ses embeddings à ceux de la campagne (incident revue #210 :
# dataprep sur une config d'embeddings ≠ campagne → index inutilisable, 0 chunk).
# Si le processus n'est pas lisible (dataprep distant, --config absent), on
# LOGGUE l'anomalie sans bloquer — la vraie solution est une API de métadonnées
# côté dataprep (issue dédiée), en attendant la vérification revient à l'humain.
cfg_get_in() { grep -E "^[[:space:]]*$2:" "$1" 2>/dev/null | head -1 | sed 's/^[^:]*:[[:space:]]*//; s/"//g'; }
if lsof -nP -iTCP:8001 -sTCP:LISTEN >/dev/null 2>&1; then
  DP_PID=$(lsof -nP -tiTCP:8001 -sTCP:LISTEN 2>/dev/null | head -1)
  DP_CFG=$(ps -o command= -p "${DP_PID:-0}" 2>/dev/null | sed -n 's/.*--config[= ]\([^ ]*\).*/\1/p')
  if [ -n "$CFG" ] && [ -n "$DP_CFG" ] && [ -f "$DP_CFG" ]; then
    DP_EMB="$(cfg_get_in "$DP_CFG" chroma_embedding_api_base)|$(cfg_get_in "$DP_CFG" chroma_embedding_model)"
    WANT="$(cfg_get chroma_embedding_api_base)|$(cfg_get chroma_embedding_model)"
    if [ "$DP_EMB" = "$WANT" ]; then
      check "DataPrep MCP (localhost:8001)" 0 "up, embeddings conformes à la campagne (config: $DP_CFG)" ""
    else
      check "DataPrep MCP (localhost:8001)" 1 "up mais embeddings ≠ campagne ($DP_EMB vs $WANT)" \
        "relancer dataprep avec la config de campagne (utilisateur) : uv run dataprep_server --config $CFG"
    fi
  elif [ -n "$CFG" ]; then
    check "DataPrep MCP (localhost:8001)" 0 "up — ANOMALIE : conformité d'embeddings NON VÉRIFIABLE (processus distant ou --config illisible) ; vérifier manuellement que dataprep porte la config de campagne" ""
  else
    check "DataPrep MCP (localhost:8001)" 0 "up (passer --config pour vérifier la conformité d'embeddings)" ""
  fi
else
  check "DataPrep MCP (localhost:8001)" 1 "aucun listener" \
    "uv run dataprep_server --config <config-de-campagne>  (à lancer par l'utilisateur)"
fi

# Embeddings — endpoint lu depuis la config si fournie (défaut historique : spark1:8003).
# Une config à embeddings cloud (api.openai.com) n'exige AUCUN service local :
# le vérifier en dur sur spark1:8003 produisait un faux blocage (validation #209).
EMB_BASE="http://spark1:8003/v1"
if [ -n "$CFG" ]; then
  CFG_EMB_BASE=$(cfg_get chroma_embedding_api_base)
  [ -n "$CFG_EMB_BASE" ] && EMB_BASE="$CFG_EMB_BASE"
fi
case "$EMB_BASE" in
  *api.openai.com*)
    check "Embeddings (cloud OpenAI)" 0 "via API OpenAI ($(cfg_get chroma_embedding_model)) — aucun service local requis" ""
    ;;
  *)
    EMB_LABEL=$(printf '%s' "$EMB_BASE" | sed -E 's|https?://||; s|/v1/?$||')
    EMB=$(curl -s --max-time 4 "${EMB_BASE%/}/models" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null)
    if [ -n "${EMB:-}" ]; then
      if [ -n "$CFG" ]; then
        WANT_EMB=$(cfg_get chroma_embedding_model)
        if [ -n "$WANT_EMB" ] && [ "$WANT_EMB" != "$EMB" ]; then
          check "Embeddings ($EMB_LABEL)" 1 "sert $EMB ≠ config ($WANT_EMB)" "aligner le serveur d'embeddings sur la config de campagne"
        else
          check "Embeddings ($EMB_LABEL)" 0 "sert: $EMB (conforme config)" ""
        fi
      else
        check "Embeddings ($EMB_LABEL)" 0 "sert: $EMB" ""
      fi
    else
      check "Embeddings ($EMB_LABEL)" 1 "injoignable" "démarrer le serveur d'embeddings ($EMB_LABEL) — utilisateur"
    fi
    ;;
esac

# vLLM (spark1:8000) — requis seulement pour les modèles Spark
VLLM=$(curl -s --max-time 4 http://spark1:8000/v1/models 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null)
if [ -n "${VLLM:-}" ]; then
  if [ -n "$CFG" ]; then
    # La config « utilise vLLM » ssi un endpoint pointe sur spark1:8000 — le
    # préfixe openai/ du nom ne suffit pas (une config OpenRouter porte name:
    # openai/… avec un base_url externe : comparer son modèle à vLLM serait un
    # faux mismatch). Guillemets OPTIONNELS partout : new_model_config.py émet
    # du YAML sans guillemets — les exiger neutralisait silencieusement la
    # garde (smoke qwen38, #223).
    WANT_MODEL=""
    if grep -qE '^[[:space:]]*base_url: "?http://spark1:8000' "$CFG" 2>/dev/null; then
      WANT_MODEL=$(grep -E '^[[:space:]]*name: "?openai/' "$CFG" 2>/dev/null | head -1 | sed 's/^[^:]*:[[:space:]]*//; s/"//g; s|^openai/||')
    fi
    if [ -z "$WANT_MODEL" ]; then
      # La config ne déclare aucun modèle servi par vLLM : ne PAS afficher
      # « conforme » (revue subagent #210 : le label masquerait un vrai défaut).
      echo "· vLLM (spark1:8000) — sert: $VLLM (non requis par cette config : campagne cloud)"
    elif [ "$WANT_MODEL" != "$VLLM" ]; then
      check "vLLM (spark1:8000)" 1 "sert $VLLM ≠ config ($WANT_MODEL)" "swap vLLM sur le modèle de la config (utilisateur)"
    else
      check "vLLM (spark1:8000)" 0 "sert: $VLLM (conforme config)" ""
    fi
  else
    check "vLLM (spark1:8000)" 0 "sert: $VLLM" ""
  fi
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
