# Tests d'intégration DGX Spark

Tests d'intégration pour valider la configuration llama.cpp sur le DGX Spark.

## Contexte

Ces tests valident **H1** (Hypothèse 1) du plan de robustification :
> Configuration llama.cpp sous-optimale causant des troncatures JSON (EOF)

**Références** :
- Issue #61: Corriger configuration llama.cpp
- Plan: `plannings/ROBUSTIFICATION_DGX_SPARK_PLAN.md` (Phase 1, S1)

## Prérequis

### 1. Accès VPN Tailscale

Les tests nécessitent un accès au DGX Spark via **Tailscale VPN** :

```bash
# Vérifier connexion Tailscale
tailscale status | grep gx10-957b

# Devrait afficher:
# gx10-957b    ... active
```

### 2. Services Docker actifs sur DGX

Les services llama.cpp doivent être lancés sur le DGX :

```bash
# Sur le DGX Spark (via SSH ou localement)
cd /path/to/agentic-research
./scripts/start-docker-dgx.sh
```

Vérifier que les services sont actifs :

```bash
docker ps | grep llm
# Devrait afficher:
# - llm-instruct (port 8002)
# - llm-reasoning (port 8004)
```

### 3. Installation dépendances

```bash
poetry install --with dev
```

## Exécution des tests

### Test de base (validation problème actuel)

Avant le fix de configuration, ce test devrait **démontrer la troncature** :

```bash
# Test service llm-instruct (gpt-oss-20b)
poetry run pytest integration_tests/test_llama_cpp_context_saturation.py::TestLlamaCppContextSaturation::test_ctx_saturation_before_fix_instruct -v -s

# Sortie attendue (AVANT fix):
# Prompt tokens: ~1500
# Current ctx-size: 2048
# Expected max output: ~548 tokens
# Output tokens: ~500-600 (TRONQUÉ)
# ✓ Troncature confirmée (comportement actuel = problème H1)
```

### Test après fix

Après avoir corrigé la configuration (`--ctx-size 4096`, `--n-predict 2048`), ce test devrait **démontrer l'absence de troncature** :

```bash
# Test validation du fix
poetry run pytest integration_tests/test_llama_cpp_context_saturation.py::TestLlamaCppContextSaturation::test_ctx_saturation_after_fix_instruct -v -s

# Sortie attendue (APRÈS fix):
# Prompt tokens: ~1500
# Target ctx-size: 4096
# Target n-predict: 2048
# Output tokens: ~1500-2000 (NON TRONQUÉ)
# ✓ Output adéquat (configuration correcte)
```

### Test stabilité JSON

Ce test valide le cas d'usage réel (génération de rapports JSON) :

```bash
poetry run pytest integration_tests/test_llama_cpp_context_saturation.py::TestLlamaCppContextSaturation::test_json_generation_stability_instruct -v -s

# Sortie attendue (APRÈS fix):
# Prompt tokens: ~300
# Output tokens: >800
# Braces balance: équilibré
# ✓ JSON generation stable (no EOF truncation)
```

### Suite complète

Pour exécuter tous les tests DGX :

```bash
# Tests DGX uniquement
poetry run pytest -m dgx -v -s

# Tests d'intégration (inclut DGX)
poetry run pytest -m integration -v -s

# Avec rapports détaillés
poetry run pytest integration_tests/test_llama_cpp_context_saturation.py -v -s --tb=short
```

## Marqueurs pytest

Les tests utilisent les marqueurs suivants :

- `@pytest.mark.integration` : Test d'intégration (services externes)
- `@pytest.mark.dgx` : Nécessite accès DGX Spark via VPN
- `@pytest.mark.slow` : Test long (>30s)

Pour ignorer les tests DGX localement :

```bash
poetry run pytest -m "not dgx"
```

## Variables d'environnement

Personnalisation optionnelle :

```bash
# Hostname DGX (défaut: gx10-957b)
export DGX_HOSTNAME=gx10-957b

# IP DGX (défaut: 100.107.87.123)
export DGX_IP=100.107.87.123
```

## Workflow TDD

### Phase 1 : Démontrer le problème (AVANT fix)

1. Lancer les services sur DGX avec config actuelle
2. Exécuter `test_ctx_saturation_before_fix_instruct`
3. **Attendu : Test PASSE** (démontre la troncature)

### Phase 2 : Appliquer le fix

1. Modifier `docker-compose.dgx.yml` :
   - Remplacer `-n 2048` par `--ctx-size 4096`
   - Ajouter `--n-predict 2048`
   - Ajouter `--batch-size 512`

2. Redémarrer les services :
   ```bash
   ./scripts/stop-docker-dgx.sh
   ./scripts/start-docker-dgx.sh
   ```

### Phase 3 : Valider le fix (APRÈS fix)

1. Exécuter `test_ctx_saturation_after_fix_instruct`
2. **Attendu : Test PASSE** (démontre l'absence de troncature)

3. Exécuter `test_json_generation_stability_instruct`
4. **Attendu : Test PASSE** (JSON complet généré)

### Phase 4 : Smoke tests complets

Exécuter 3-5 runs complets du workflow pour validation :

```bash
# Sur DGX avec nouvelle config
poetry run agentic-research --config configs/config-docker-dgx.yaml --query "Retrieval Augmented Generation" --debug

# Vérifier:
# - Pas d'erreur ModelBehaviorError
# - Pas d'EOF while parsing
# - Rapports complets générés
```

## Résolution de problèmes

### Service non accessible

```
pytest.skip: Service llama.cpp non accessible
```

**Solutions** :
- Vérifier connexion VPN Tailscale : `tailscale status`
- Vérifier services Docker : `ssh gx10-957b "docker ps"`
- Tester connectivité : `curl http://gx10-957b:8002/health`

### Tests skip automatiquement

Les tests sont marqués `@pytest.mark.dgx` et peuvent être skippés dans CI/CD.
Pour forcer l'exécution locale :

```bash
poetry run pytest -m dgx --runxfail -v -s
```

### Timeout

Si les tests timeout (>60s), augmenter dans le code :

```python
response = self._make_completion_request(
    endpoint=instruct_endpoint,
    prompt=prompt,
    n_predict=2048,
    timeout=120,  # Augmenter si nécessaire
)
```

## Références

- **Issue #61** : https://github.com/BittnerPierre/agentic-research/issues/61
- **Plan de robustification** : `plannings/ROBUSTIFICATION_DGX_SPARK_PLAN.md`
- **Docker compose DGX** : `docker-compose.dgx.yml`
- **Scripts DGX** : `scripts/start-docker-dgx.sh`, `scripts/stop-docker-dgx.sh`
