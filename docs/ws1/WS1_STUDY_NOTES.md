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
| **GPT-OSS** (vLLM) | `--reasoning-parser openai_gptoss` | `reasoning_effort` au top-level du payload ✅ (validé spike 2026-04-17) |
| **OpenAI cloud** | N/A | `reasoning_effort` param natif |
| **Nemotron** | `--reasoning-parser nemotron_v3` | `extra_body={"chat_template_kwargs": {"enable_thinking": True}}` |
| **Qwen 3** | `--enable-reasoning --reasoning-parser deepseek_r1` | `/think` dans le user input |
| **Mistral** | Pas de mode reasoning explicite | Sampling params uniquement |

### Résultats du spike (2026-04-17, gpt-oss-20b sur vLLM solo, GB10 Spark)

**Setup validé** : image standard `vllm-node` (build eugr sans `--exp-mxfp4`),
lancée via `./launch-cluster.sh --solo`, port 8010, sans
`VLLM_USE_FLASHINFER_MOE_MXFP4_MXFP8=1` (voir pièges ci-dessous).

**Mesures reasoning_effort** (même prompt, `max_tokens=2048`, `temperature=0`) :

| `reasoning_effort` | completion_tokens | reasoning_chars | content_chars |
|--------------------|-------------------|-----------------|---------------|
| low                | 881               | 703             | 1536          |
| medium             | 1334              | 1737            | 1670          |
| high               | 2048 **(cap)**    | 7028            | **0** ⚠️     |

- Impact monotone, très fort : low → medium ≈ ×2,5 ; medium → high ≈ ×4
- `reasoning_effort=high` avec un `max_tokens` trop bas **cape avant la
  réponse finale** → `content` vide. Provisionner large (≥ 8k pour high).
- Le parser `openai_gptoss` sépare bien `message.reasoning` de
  `message.content` dans la réponse JSON.

**Pièges rencontrés (à retenir pour tout run vLLM sur GB10/sm_121)** :

1. `VLLM_USE_FLASHINFER_MOE_MXFP4_MXFP8=1` fait lever :
   > `Mxfp4 MoE backend 'FLASHINFER_TRTLLM_MXFP4_MXFP8' does not support the deployment configuration since kernel does not support current device cuda.`
   Ce backend est incompatible avec sm_121. **Ne pas forcer cet env var** —
   vLLM auto-sélectionne un backend compatible (Triton) sans.
   Cet env var reste pertinent sur le build `--exp-mxfp4` (optimisé CUTLASS).

2. L'exemple `examples/vllm-openai-gpt-oss-120b.sh` d'eugr contient cet
   env var — il a été écrit pour le build optimisé et le cluster dual-Spark,
   pas pour un setup solo + image standard.

### Contrat agent (décidé)

Champ `reasoning_effort` à ajouter dans `ModelEndpointConfig`
(`src/config.py`), valeurs `low | medium | high | null`.
Passé tel quel au top-level du payload OpenAI-compatible (pas dans
`extra_body`). Compatible avec les autres familles via un mapping à faire
dans les agents (Nemotron → `chat_template_kwargs`, Qwen → injection prompt).

### Taille de contexte et réserve output

vLLM n'a pas d'équivalent direct à `--n-predict` (llama.cpp) qui garantit
côté serveur une réserve de tokens pour la génération. Le découpage
prompt/output est piloté **côté client** via `max_tokens`. Implication :
pour un agent avec `reasoning_effort=high`, il faut provisionner
`max_tokens` large (8k+) sinon la réponse finale est tronquée après le
reasoning.

| llama.cpp | vLLM | Rôle |
|-----------|------|------|
| `--ctx-size` | `--max-model-len` | Contexte total (prompt + output) côté serveur |
| `--n-predict` | *(pas d'équivalent serveur)* | Réserve output — côté client via `max_tokens` |

### Spike réalisé le 2026-04-17 ✅

Spike effectué avec gpt-oss-**20b** (pas 120B) sur le Spark solo, image vLLM
standard eugr. Questions ouvertes résolues :
- Mécanisme reasoning gpt-oss vLLM → `reasoning_effort` top-level + parser
  `openai_gptoss`
- Abstraction côté agent → Option A confirmée (`ModelEndpointConfig`)
- Build à utiliser pour multi-modèles → image standard (pas `--exp-mxfp4`)

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
