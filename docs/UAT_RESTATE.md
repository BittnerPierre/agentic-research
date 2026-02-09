# UAT Restate + agentic-research (Local et DGX)

Ce guide decrit le parcours UAT pour valider Restate dans le POC Writer, en parallele du run agentic-research.

## Portee

- Restate est active pour le service Writer (POC).
- Le workflow deep_manager peut utiliser Restate pour le Writer via env vars.
- Objectif UAT: valider la resilience et l observabilite sur le Writer Restate, et verifier que
  le run agentic-research continue a fonctionner normalement.

## Pre-requis

- Docker fonctionne.
- `models.env` configure (copie de `models.env.example`).
- Restate CLI installe (ou disponible en binaire local).
  - Voir la doc Restate pour l installation du CLI: https://docs.restate.dev/installation

## 1) Local (CPU)

### 1.1 Demarrer le stack

```
bash scripts/start-docker-local.sh
```

Services attendus:
- restate (8080/9070/9071)
- writer-restate (9080)
- chromadb, dataprep, llama-cpp-cpu

### 1.2 Enregistrer le writer service

```
restate deployments register http://writer-restate:9080 -y --use-http1.1 --force
```

Alternative via image CLI (si le binaire `restate` n est pas installe en local):
```
docker run --rm --network agentic-research_default \
  -e RESTATE_ADMIN_URL=http://restate:9070 \
  docker.restate.dev/restatedev/restate-cli:latest \
  deployments register http://writer-restate:9080 -y --use-http1.1 --force
```

Verifier dans l UI:
- http://localhost:9070
- service `WriterAgentRestate` visible avec handler `run`

### 1.3 UAT Restate (Writer)

Invocation nominale:
```
curl -s -X POST http://localhost:8080/WriterAgentRestate/run \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Ecris un court rapport de test.",
    "research_info": {
      "temp_dir": "/tmp",
      "output_dir": "/tmp/restate-output",
      "max_search_plan": "1",
      "vector_store_name": null,
      "vector_store_id": null,
      "search_results": []
    }
  }'
```

Crash + reprise:
```
curl -s -X POST http://localhost:8080/WriterAgentRestate/run/send \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Rapport long pour tester la reprise.",
    "research_info": {
      "temp_dir": "/tmp",
      "output_dir": "/tmp/restate-output",
      "max_search_plan": "1",
      "vector_store_name": null,
      "vector_store_id": null,
      "search_results": []
    }
  }'
```

Puis simuler un crash du writer:
```
docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file models.env restart writer-restate
```

Verifier le statut:
```
restate invocations list
restate invocations describe <INVOCATION_ID>
```

### 1.4 UAT agentic-research (sans Restate)

```
docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file models.env run --rm agentic-research \
  agentic-research --config /app/configs/config-docker-local.yaml \
  --query "Your research question"
```

Note: le writer est appele via Restate si `RESTATE_WRITER_ENABLED=true` (defaut dans docker-compose.yml).

## 2) DGX (GPU)

### 2.1 Demarrer le stack

```
bash scripts/start-docker-dgx.sh
```

### 2.2 Enregistrer le writer service

```
restate deployments register http://writer-restate:9080 -y --use-http1.1 --force
```

Alternative via image CLI (si le binaire `restate` n est pas installe en local):
```
docker run --rm --network agentic-research_default \
  -e RESTATE_ADMIN_URL=http://restate:9070 \
  docker.restate.dev/restatedev/restate-cli:latest \
  deployments register http://writer-restate:9080 -y --use-http1.1 --force
```

### 2.3 UAT Restate (Writer)

Invocation nominale (meme commande que local).

### 2.4 UAT agentic-research (sans Restate)

```
docker compose -f docker-compose.yml -f docker-compose.dgx.yml --env-file models.env run --rm agentic-research \
  agentic-research --config /app/configs/config-docker-dgx.yaml \
  --query "Your research question"
```

Note: le writer est appele via Restate si `RESTATE_WRITER_ENABLED=true` (defaut dans docker-compose.yml).

## Notes

- Pour l instant, Restate couvre le Writer POC. L integration complete du workflow sera une etape suivante.
- La doc Restate officielle illustre la structure d un durable agent:
  https://docs.restate.dev/tour/openai-agents#creating-a-durable-agent
