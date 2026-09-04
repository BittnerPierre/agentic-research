#!/bin/bash
# Batterie de campagne : N runs séquentiels par exercice, correction complète
# après chaque run, résolution AUTORITAIRE du dossier de run (stats.json
# output_dir — jamais « le dernier dossier », une collision entre batteries
# parallèles a déjà été observée).
#
# Usage: run_battery.sh <config.yaml> <tag> <finance|concept|both> [N=5] [--skip-judge]
#   tag     : préfixe des runs (ex: camp-mistral) → collections/output camp-mistral-capex-1…
#   N       : nombre de runs par exercice (1 à n, défaut 5)
# Sortie   : benchmarks/summaries/<tag>_results.txt (+ echo à la fin)
#
# Séquentiel par design : vLLM ne sert qu'un modèle, et deux batteries
# parallèles ne posent problème QUE si elles partagent le tag (collections
# distinctes par run sinon). Cloud + Spark en parallèle : OK.
set -u -o pipefail
CFG="$1"; TAG="$2"; WHICH="$3"; N="${4:-5}"; JUDGE_FLAG="${5:-}"
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
mkdir -p benchmarks/summaries
SUMMARY="benchmarks/summaries/${TAG}_results.txt"
: > "$SUMMARY"

find_run() { # retrouve le dossier de run par son output_dir (autoritaire)
  uv run python -c "
import json, glob, os
for sp in sorted(glob.glob('benchmarks/runs/*/stats.json'), key=os.path.getmtime, reverse=True):
    try: d = json.load(open(sp))
    except Exception: continue
    if os.path.basename((d.get('output_dir') or '').rstrip('/')) == '$1':
        print(os.path.dirname(sp)); break"
}

do_run() {
  local name="$1" syllabus="$2" exercise="$3"
  local t0=$SECONDS
  echo "[battery] $name : début $(date '+%H:%M:%S')" >> "$SUMMARY"
  uv run agentic-research --config "$CFG" --syllabus "$syllabus" \
    --output-dir "output/$name" --vector-store "$name" > "benchmarks/summaries/${name}.log" 2>&1
  if [ $? -ne 0 ]; then
    echo "[battery] ÉCHEC run $name — voir benchmarks/summaries/${name}.log" >> "$SUMMARY"
    return 1
  fi
  local run; run=$(find_run "$name")
  if [ -z "$run" ]; then echo "[battery] $name : dossier de run introuvable" >> "$SUMMARY"; return 1; fi
  echo "=== $name ($run) wall=$((SECONDS - t0))s" >> "$SUMMARY"
  local extra=""
  [ "$JUDGE_FLAG" = "--skip-judge" ] && extra="--skip-semantic-judge"
  # revue Codex #2 : le code retour du scorer ne doit pas être avalé par le
  # pipeline — correction dans un fichier temporaire, rc vérifié, puis filtrage.
  local gout="benchmarks/summaries/${name}.grade.out"
  if uv run python -m evaluations.deterministic_grade "$run" \
    --exercise "evaluations/exercises/$exercise" $extra > "$gout" 2>&1; then
    grep -iv pydantic "$gout" | tail -12 >> "$SUMMARY"  # -i : __pydantic_serializer__ passait (#223)
    # Lisibilité console (revue subagent #210) : un evaluation_failed n'est pas
    # un zéro, et une note peut cacher un pack non qualifié — le dire ICI, sans
    # obliger le lecteur à ouvrir det_grade.json.
    uv run python -c "
import json, sys
try:
    d = json.load(open(sys.argv[1] + '/det_grade.json'))
except Exception:
    sys.exit(0)
verdict = (d.get('root_cause') or {}).get('verdict') or ''
q = d.get('qualification') or {}
blockers = ', '.join((q.get('blockers') or []) + (q.get('format_blockers') or []))
if verdict == 'evaluation_failed':
    print('[battery] ATTENTION : évaluation NON ABOUTIE (lettre E) — le SCORE ci-dessus')
    print('[battery] n\'est pas une note. Blockers :', blockers[:200] or 'voir det_grade.json')
elif d.get('qualified') is False:
    print('[battery] réserve : pack NON QUALIFIÉ malgré le score —', blockers[:200] or 'voir det_grade.json')
" "$run" >> "$SUMMARY"
  else
    echo "[battery] ÉCHEC CORRECTION $name (rc≠0) — voir $gout" >> "$SUMMARY"
  fi
  echo >> "$SUMMARY"
}

run_series() {
  local kind="$1" syllabus="$2" exercise="$3"
  for i in $(seq 1 "$N"); do
    do_run "${TAG}-${kind}-${i}" "$syllabus" "$exercise"
  done
}

# Contrôle du corpus gelé AVANT tout appel modèle (revue Codex #210, finding 3 :
# un drift de hash découvert après coup a coûté un run conceptuel complet).
verify_corpus() {
  uv run python evaluations/campaign/scripts/verify_corpus.py "evaluations/exercises/$1" \
    | tee -a "$SUMMARY"
  if [ "${PIPESTATUS[0]}" -ne 0 ]; then
    echo "[battery] ABANDON avant appel modèle : corpus gelé non conforme ($1)" | tee -a "$SUMMARY"
    exit 1
  fi
}

case "$WHICH" in
  finance)
    verify_corpus "ai-capex-intensity"
    run_series "capex" "evaluations/exercises/ai-capex-intensity/syllabus.md" "ai-capex-intensity" ;;
  concept)
    verify_corpus "ai-engineering-syllabus"
    run_series "concept" "evaluations/exercises/ai-engineering-syllabus/syllabus.md" "ai-engineering-syllabus" ;;
  both)
    verify_corpus "ai-engineering-syllabus"
    verify_corpus "ai-capex-intensity"
    run_series "concept" "evaluations/exercises/ai-engineering-syllabus/syllabus.md" "ai-engineering-syllabus"
    run_series "capex" "evaluations/exercises/ai-capex-intensity/syllabus.md" "ai-capex-intensity"
    ;;
  *) echo "exercice inconnu: $WHICH (finance|concept|both)"; exit 2 ;;
esac
echo "[battery] terminé : $(date '+%H:%M:%S')" >> "$SUMMARY"
cat "$SUMMARY"
