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

### Principe : composition (backend × topologie × modèle)

La stack d'inférence est une **composition de services** fonction de l'usage.
Les choix sont orthogonaux :

- **Backend d'inférence** : llama.cpp, vLLM, SGLang, … (chacun expose
  une API OpenAI-compatible)
- **Topologie** : mono-modèle, split instruct/reasoning, combo vision+voice+llm, …
- **Modèle(s)** : gpt-oss-20b, gpt-oss-120B, Nemotron, Qwen 3, …

Cette décomposition existe déjà structurellement dans le repo :

| Couche | Où | Rôle |
|--------|----|----|
| Infra | `docker-compose.*.yml` + `models/*.env` | Quels services, quel backend, quels modèles |
| Agentic | `configs/*.yaml` | Quel endpoint pour quel agent |

Le workflow agentic ne voit que des URLs OpenAI-compatibles — il n'a pas à
savoir ce qu'il y a derrière. Chaque combo (backend × topologie × modèle) =
un triplet **compose + env + config**.

### Combos cibles WS1

| Combo | compose | env | config | Statut |
|-------|---------|-----|--------|--------|
| llama.cpp split (existant) | `docker-compose.dgx.yml` | `models/models.openai.env` | `config-docker-dgx.yaml` | ✅ en place |
| **vLLM split, gpt-oss-20b** (cible immédiate) | `docker-compose.dgx-vllm-split.yml` | `models/models.vllm-gptoss20b-split.env` | `config-docker-dgx-vllm-split.yaml` | ⏳ à créer |
| vLLM mono, gpt-oss-120B | `docker-compose.dgx-vllm-mono.yml` | `models/models.vllm-gptoss120b-mono.env` | `config-docker-dgx-vllm-mono.yaml` | 🟡 scaffoldé |

Autres compositions possibles à l'avenir : SGLang, vision+voice+llm, etc.
Le pattern de nommage `<host>-<backend>-<topologie>` reste extensible.

### Reasoning effort au niveau agent (pour le mono-modèle)

Dans le combo mono-modèle, le même modèle sert tous les agents — le reasoning
effort doit donc être contrôlé **par agent** (le planner a besoin de plus de
reasoning que le search agent), au lieu d'être figé côté serveur.
Dans le combo split (étape intermédiaire), on peut continuer à piloter le
reasoning côté serveur comme aujourd'hui.

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

### Stratégie : split-first, mono ensuite

On change **une variable à la fois** :

1. D'abord le backend d'inférence (llama.cpp → vLLM) **sans** toucher à la
   topologie ni au modèle → on valide vLLM isolément avec gpt-oss-20b dans
   le split actuel (2 services `llm-instruct` + `llm-reasoning`).
2. Ensuite seulement, on passe à la topologie mono-modèle avec gpt-oss-120B
   → changement de topologie + changement de modèle + reasoning par agent.

Bénéfice : en cas de régression on sait quelle variable incriminer, et on
peut comparer split vLLM vs split llama.cpp à iso-modèle/iso-topologie.

### Baby steps (validation à chaque étape)

| # | Étape | Livrable | Critère de succès |
|---|-------|----------|-------------------|
| 0 | Doc : trajectoire, référence eugr, schéma de nommage | Ce document | Relu et validé |
| 1 | Spike vLLM standalone (hors compose) : image pour GB10/aarch64, `curl /v1/models` + chat/completions avec gpt-oss-20b | Commandes + image fonctionnelle | API vLLM répond |
| 2 | Spike reasoning : découvrir le mécanisme vLLM pour gpt-oss (parser ? `extra_body` ? `chat_template_kwargs` ?) | Section "reasoning vLLM gpt-oss" ajoutée à ce doc | Paramètre identifié |
| 3 | Combo **vLLM split gpt-oss-20b** : `docker-compose.dgx-vllm-split.yml` + `models/models.vllm-gptoss20b-split.env` | Compose + env | `docker compose up` OK, les 2 endpoints répondent |
| 4 | Config agentic : `configs/config-docker-dgx-vllm-split.yaml` (copie de `config-docker-dgx.yaml`, pas de code agent modifié) | Config | — |
| 5 | Run end-to-end `agentic-research` sur le combo split vLLM | Trace + rapport | Workflow termine sans erreur |
| 6 | Benchmark split vLLM vs split llama.cpp (iso config agentic) | Chiffres comparatifs | Résultats publiés |
| 7 | **Point de décision** : on attaque le mono-modèle ? | Go/No-Go | — |
| 8 | Refactor agent : `reasoning_effort` par agent dans `ModelEndpointConfig` | PR code + tests | Tests passent |
| 9 | Combo **vLLM mono gpt-oss-120B** (scaffolding déjà en place) : validation end-to-end | Run complet | Workflow OK |

Stretch (après step 9) : Nemotron, Qwen 3, Gemma 4, éventuellement SGLang.

### Mapping issues GitHub

- **S1-03 #152** (Setup vLLM) couvre les steps 1-5
- **S1-04 #149** (Validation mono-modèle) couvre les steps 6-9
- **S1-02 #95** (Hash syllabus) indépendant, à caler quand souhaité

### Contraintes

- **Tout doit fonctionner sur le workflow actuel** (pas de dépendance à WS4)
- **Branche de workstream** : `ws1/inference-platform`
- **Engagement client ASUS/NVIDIA** : livraison requise

---

## 5. Fichiers clés à modifier

### Combo vLLM split gpt-oss-20b (steps 3-5)

| Fichier | Changement |
|---------|------------|
| `docker-compose.dgx-vllm-split.yml` | Nouveau : 2 services vLLM (instruct + reasoning) |
| `configs/config-docker-dgx-vllm-split.yaml` | Nouveau : copie du split llama.cpp existant |
| `models/models.vllm-gptoss20b-split.env` | Nouveau : env vLLM split gpt-oss-20b |

### Combo vLLM mono gpt-oss-120B (steps 8-9, scaffoldé)

| Fichier | État |
|---------|------|
| `docker-compose.dgx-vllm-mono.yml` | 🟡 scaffoldé, TODOs à lever au step 9 |
| `configs/config-docker-dgx-vllm-mono.yaml` | 🟡 scaffoldé |
| `models/models.vllm-gptoss120b-mono.env` | 🟡 scaffoldé |
| `scripts/start-docker-dgx-vllm-mono.sh` | 🟡 scaffoldé |
| `src/config.py` | `ModelEndpointConfig.reasoning_effort` (step 8) |
| `src/agents/utils.py` | Passer `reasoning_effort` aux `model_settings` (step 8) |

### Inchangé

| Fichier | Pourquoi |
|---------|----------|
| `docker/Dockerfile.llamacpp` | llama.cpp reste un backend supporté, pas remplacé |
| `docker-compose.dgx.yml` | Combo llama.cpp split reste disponible |

---

## 6. Références

- **vLLM Docker pour Spark (référence build GB10/aarch64)** :
  https://github.com/eugr/spark-vllm-docker
- gpt-oss-20b (modèle étapes 1-6) : https://huggingface.co/openai/gpt-oss-20b
- gpt-oss-120b (modèle étape 9) : https://huggingface.co/openai/gpt-oss-120b
- Nemotron reasoning (stretch) :
  https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4
- Config DGX actuelle (baseline llama.cpp split) :
  `docker-compose.dgx.yml` + `configs/config-docker-dgx.yaml`
