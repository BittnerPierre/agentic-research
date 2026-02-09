# HOW-TO: Simuler des erreurs Restate (POC Writer)

Objectif: fournir un petit guide pour reproduire des erreurs et observer la reprise Restate.

Prerequis:
- Restate Server en container (ports 8080/9070 publies).
- Writer service en local (ASGI) et enregistre dans Restate.
- Config writer: `configs/tests/config-dgx-remote.yaml`.

## 1) Demarrage

Restate (container):
```
docker run --name restate_dev --rm -p 8080:8080 -p 9070:9070 -p 9071:9071 \
  --add-host=host.docker.internal:host-gateway \
  docker.restate.dev/restatedev/restate:latest
```

Writer service (local):
```
RESTATE_WRITER_CONFIG=configs/tests/config-dgx-remote.yaml \
  poetry run python scripts/restate_writer_service.py
```

Enregistrement service (depuis le host, Restate en container):
```
/tmp/restate-bin/restate-cli-aarch64-apple-darwin/restate deployments register \
  http://192.168.65.254:9080 -y --use-http1.1 --force
```

## 2) Invocation nominale (sanity check)

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

## 3) Simulation crash + reprise

1) Demarrer une invocation asynchrone:
```
curl -s -X POST http://localhost:8080/WriterAgentRestate/run/send \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Ecris un rapport plus long pour tester un redemarrage.",
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

2) Couper le writer service (simuler crash):
```
kill <PID_WRITER>
```

3) Relancer le writer service:
```
RESTATE_WRITER_CONFIG=configs/tests/config-dgx-remote.yaml \
  poetry run python scripts/restate_writer_service.py
```

4) Verifier l invocation:
```
/tmp/restate-bin/restate-cli-aarch64-apple-darwin/restate invocations list
/tmp/restate-bin/restate-cli-aarch64-apple-darwin/restate invocations describe <INVOCATION_ID>
```

Attendu: l invocation passe en `completed with success` apres relance.

## 4) Simulation timeout LLM (proposition)

Approche simple: configurer un modele/endpoint lent ou indisponible, puis lancer une invocation.

Exemples:
- Pointer `writer_model.base_url` vers un host inexistant temporairement.
- Redemarrer le writer service puis relancer l invocation.

Attendu: l invocation est en retry puis en erreur (ou reprise si l endpoint revient).

## 5) Simulation tool error (proposition)

Le writer actuel n appelle pas de tool dans le flux POC.

Option simple:
- Ajouter un tool durable qui echoue volontairement (1er appel).
- Relancer le writer et observer la reprise/restauration via Restate.

Si tu veux, je peux ajouter un flag d injection pour forcer ces erreurs.
