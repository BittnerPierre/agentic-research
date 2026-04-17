# WS1 - Inference Platform - Notes d'étude

## Objectif

Faire tourner `agentic-research` sur un **seul gros modèle instruct + reasoning**
via **vLLM** sur dual DGX Spark, en commençant par `gpt-oss-120B`.

Ce document sert de référence de travail pour le workstream WS1.

---

## 1. Situation actuelle

### Backend : llama.cpp

Le projet utilise exclusivement **llama.cpp** comme backend d'inférence locale :

- Docker image custom (`docker/Dockerfile.llamacpp`) compilée avec CUDA
- Entrypoint shell (`docker/llama-server-entrypoint.sh`) avec injection d'`EXTRA_PARAMS`
- Modèles au format GGUF (quantisés)
- API OpenAI-compatible (`/v1/chat/completions`, `/v1/embeddings`)

### Architecture multi-modèle (split)

Le setup DGX actuel utilise **3 services séparés** :

| Service | Port | Rôle | Modèle actuel |
|---------|------|------|---------------|
| `llm-instruct` | 8002 | Research, search, writer, knowledge_prep | gpt-oss-20b-mxfp4 |
| `llm-reasoning` | 8004 | Planning | gpt-oss-20b (+ reasoning_effort) |
| `embeddings-gpu` | 8003 | Embeddings | Qwen3-Embedding-4B-Q8_0 |

Le reasoning effort est passé via `--chat-template-kwargs {"reasoning_effort":"medium"}`
au niveau du **serveur** llama.cpp (pas au niveau agent).

### Configuration

- `configs/config-docker-dgx.yaml` : config Docker interne
- `configs/tests/config-dgx-remote.yaml` : config remote (hostname `gx10-957b`)
- `models/models.openai.env` : chemins modèles + params serveur
- Chaque agent a son propre `model_spec` dans la config YAML

---

## 2. Cible WS1

### Architecture mono-modèle

Un seul service d'inférence avec un gros modèle qui fait tout (instruct + reasoning) :

| Service | Port | Rôle | Modèle cible |
|---------|------|------|-------------|
| `llm` (vLLM) | 8002 | Tous les agents | gpt-oss-120B |
| `embeddings-gpu` | 8003 | Embeddings | Qwen3-Embedding-4B (inchangé) |

### Reasoning effort au niveau agent

Au lieu de le passer au serveur, le reasoning effort doit être contrôlé
**par agent** (le planner a besoin de plus de reasoning que le search agent).

---

## 3. Étude : reasoning effort par famille de modèles

### Problème

Chaque famille de modèles a un mécanisme différent pour activer/contrôler
le reasoning :

| Famille | Mécanisme serveur | Mécanisme prompt/API |
|---------|-------------------|---------------------|
| **GPT-OSS** (llama.cpp) | `--chat-template-kwargs {"reasoning_effort":"medium"}` | Non disponible côté API |
| **GPT-OSS** (vLLM) | À étudier | À étudier |
| **OpenAI cloud** | N/A | `reasoning_effort` param natif |
| **Nemotron** | `--reasoning-parser nemotron_v3` | `extra_body={"chat_template_kwargs": {"enable_thinking": True}}` |
| **Qwen 3** | `--enable-reasoning --reasoning-parser deepseek_r1` | `/think` dans le user input |
| **Mistral** | Pas de mode reasoning explicite | Sampling params uniquement |

### Questions ouvertes

1. **vLLM + gpt-oss-120B** : comment passer le reasoning effort ?
   - vLLM supporte-t-il `chat_template_kwargs` ?
   - Faut-il un `--reasoning-parser` spécifique ?
   - Ou est-ce géré par le chat template du modèle ?

2. **Abstraction côté agent** : quel contrat ?
   - Option A : champ `reasoning_effort` dans `ModelEndpointConfig` (config YAML)
   - Option B : paramètre dans `ModelSettings` des agents SDK
   - Option C : injection dans le prompt (comme Qwen `/think`)
   - Recommandation probable : **Option A** car plus propre et compatible avec
     le pattern existant de config par agent

3. **Compatibilité** : le mécanisme choisi doit fonctionner avec :
   - le workflow multi-modèles actuel (WS4 le merge ensuite)
   - les benchmarks existants
   - les modèles stretch (Nemotron, Qwen 3)

### Action : spike sur le Spark

Tester directement sur le DGX Spark :
1. Lancer vLLM avec gpt-oss-120B
2. Vérifier l'API de reasoning (params supportés)
3. Documenter le mécanisme effectif
4. Proposer l'abstraction

---

## 4. Plan de travail WS1

### Phase 1 : Setup vLLM (S1-03 #152)

- [ ] Créer `docker-compose.dgx-vllm.yml` avec service vLLM
- [ ] Créer `configs/config-docker-dgx-vllm.yaml` pour mode mono-modèle
- [ ] Créer `models/models.vllm-gptoss120b.env`
- [ ] Référence : https://github.com/eugr/spark-vllm-docker
- [ ] Tester que le service démarre et sert l'API OpenAI-compatible
- [ ] Documenter la config

### Phase 2 : Validation mono-modèle (S1-04 #149)

- [ ] Spike reasoning effort : note d'étude (voir section 3)
- [ ] Faire tourner `agentic-research` sur gpt-oss-120B via vLLM
- [ ] Comparer avec le setup split llama.cpp actuel si pertinent
- [ ] Stretch : tester Nemotron, Qwen 3, Gemma 4
- [ ] Produire la note de décision technique

### Phase 3 : Hash syllabus (S1-02 #95)

- [ ] Ajouter le hash du syllabus dans les artefacts benchmark
- [ ] Peut être fait indépendamment des phases 1-2

### Contraintes

- **Tout doit fonctionner sur le workflow actuel** (pas de dépendance à WS4)
- **Branche de workstream** : `ws1/inference-platform`
- **Engagement client ASUS/NVIDIA** : livraison requise

---

## 5. Fichiers clés à modifier

| Fichier | Changement |
|---------|------------|
| `docker-compose.dgx-vllm.yml` | Nouveau : compose vLLM |
| `configs/config-docker-dgx-vllm.yaml` | Nouveau : config mono-modèle |
| `models/models.vllm-gptoss120b.env` | Nouveau : env vLLM |
| `src/config.py` | Éventuellement : champ reasoning_effort dans ModelEndpointConfig |
| `src/agents/utils.py` | Éventuellement : passer reasoning_effort aux model_settings |
| `docker/Dockerfile.llamacpp` | Inchangé (llama.cpp reste supporté) |

---

## 6. Références

- vLLM Docker pour Spark : https://github.com/eugr/spark-vllm-docker
- Nemotron reasoning : https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4
- gpt-oss-120B GGUF : déjà référencé dans `models/models.openai.env` (commenté)
- Config DGX actuelle : `docker-compose.dgx.yml` + `configs/config-docker-dgx.yaml`
