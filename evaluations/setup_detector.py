"""
Setup Detector - Détecte et parse le setup actif via models.env

Ce module détecte automatiquement le setup de modèles actif en résolvant
le symlink models.env et en parsant le fichier .env correspondant.
"""

import os
import re


def detect_active_setup(models_env_path: str = "models/models.env") -> dict:
    """
    Détecte le setup actif via le symlink models.env et parse les métadonnées.

    Peut aussi être spécifié via la variable d'environnement BENCHMARK_SETUP_NAME.

    Args:
        models_env_path: Chemin vers le fichier models.env (défaut: "models.env")

    Returns:
        {
            "setup_name": "ministral",
            "models_env_file": "models.ministral.env",
            "models": {
                "instruct": {
                    "path": ".../Ministral-3-14B-Instruct-2512-Q4_K_M.gguf",
                    "quantization": "Q4_K_M",
                    "ctx_size": "32768",
                    "extra_params": "--flash-attn on"
                },
                "reasoning": {...},
                "embeddings": {...}
            }
        }

    Raises:
        FileNotFoundError: Si models.env n'existe pas
        ValueError: Si le format du fichier .env est invalide
    """
    # Vérifier si le setup est fourni via variable d'environnement
    setup_name_env = os.environ.get("BENCHMARK_SETUP_NAME")
    if setup_name_env:
        setup_name = setup_name_env
        real_path = f"models/models.{setup_name}.env"
        if not os.path.exists(real_path):
            raise FileNotFoundError(
                f"Model config file not found: {real_path}. "
                f"BENCHMARK_SETUP_NAME={setup_name_env} is set but file does not exist."
            )
    else:
        # Vérifier que le fichier existe
        if not os.path.exists(models_env_path):
            raise FileNotFoundError(
                f"models.env not found at {models_env_path}. "
                "Please create a symlink: ln -sf models.<setup>.env models.env"
            )

        # Résoudre le symlink pour obtenir le fichier réel
        real_path = os.path.realpath(models_env_path)

        # Extraire le nom du setup
        setup_name = extract_setup_name(real_path)

    # Parser le fichier .env
    env_data = parse_env_file(real_path)

    return {
        "setup_name": setup_name,
        "models_env_file": os.path.basename(real_path),
        "models": env_data,
    }


def extract_setup_name(env_file_path: str) -> str:
    """
    Extrait le nom du setup depuis le path du fichier .env.

    Args:
        env_file_path: Chemin complet vers le fichier (ex: /path/to/models.ministral.env)

    Returns:
        Nom du setup (ex: "ministral")

    Examples:
        >>> extract_setup_name("/home/user/models.ministral.env")
        "ministral"
        >>> extract_setup_name("models.qwen.env")
        "qwen"
    """
    filename = os.path.basename(env_file_path)

    # Pattern: models.<setup_name>.env
    match = re.match(r"models\.(.+)\.env", filename)
    if not match:
        raise ValueError(
            f"Invalid models.env filename format: {filename}. "
            "Expected format: models.<setup_name>.env"
        )

    return match.group(1)


def parse_env_file(env_file_path: str) -> dict:
    """
    Parse le fichier .env et extrait les métadonnées des modèles.

    Args:
        env_file_path: Chemin vers le fichier .env

    Returns:
        {
            "instruct": {
                "path": "...",
                "quantization": "Q4_K_M",
                "ctx_size": "32768",
                "extra_params": "--flash-attn on"
            },
            "reasoning": {...},
            "embeddings": {...}
        }
    """
    env_vars = _load_env_file(env_file_path)

    models = {}

    # Parser Instruct model
    if "LLM_INSTRUCT_MODEL_PATH" in env_vars:
        models["instruct"] = {
            "path": env_vars["LLM_INSTRUCT_MODEL_PATH"],
            "quantization": extract_quantization(env_vars["LLM_INSTRUCT_MODEL_PATH"]),
            "ctx_size": env_vars.get("LLM_INSTRUCT_CTX_SIZE", "N/A"),
            "extra_params": env_vars.get("LLM_INSTRUCT_EXTRA_PARAMS", ""),
        }

    # Parser Reasoning model
    if "LLM_REASONING_MODEL_PATH" in env_vars:
        models["reasoning"] = {
            "path": env_vars["LLM_REASONING_MODEL_PATH"],
            "quantization": extract_quantization(env_vars["LLM_REASONING_MODEL_PATH"]),
            "ctx_size": env_vars.get("LLM_REASONING_CTX_SIZE", "N/A"),
            "extra_params": env_vars.get("LLM_REASONING_EXTRA_PARAMS", ""),
        }

    # Parser Embeddings model
    if "EMBEDDINGS_MODEL_PATH" in env_vars:
        models["embeddings"] = {
            "path": env_vars["EMBEDDINGS_MODEL_PATH"],
            "quantization": extract_quantization(env_vars["EMBEDDINGS_MODEL_PATH"]),
        }

    return models


def extract_quantization(gguf_path: str) -> str:
    """
    Extrait la quantization depuis le nom du fichier .gguf.

    Args:
        gguf_path: Chemin complet vers le fichier .gguf

    Returns:
        Quantization (ex: "Q4_K_M", "Q8_0", "mxfp4")

    Examples:
        >>> extract_quantization("Ministral-3-14B-Instruct-2512-Q4_K_M.gguf")
        "Q4_K_M"
        >>> extract_quantization("gpt-oss-20b-mxfp4.gguf")
        "mxfp4"
        >>> extract_quantization("Qwen3-Embedding-4B-Q8_0.gguf")
        "Q8_0"
    """
    filename = os.path.basename(gguf_path)

    # Pattern 1: Q<number>_<variant> (ex: Q4_K_M, Q8_0)
    # Cherche le pattern complet avec underscores jusqu'au .gguf
    match = re.search(r"-(Q\d+(?:_[A-Z0-9]+)*)", filename)
    if match:
        return match.group(1)

    # Pattern 2: mxfp<number> (ex: mxfp4)
    match = re.search(r"-(mxfp\d+)", filename)
    if match:
        return match.group(1)

    # Pattern 3: BF16
    if "BF16" in filename:
        return "BF16"

    # Si aucun pattern trouvé
    return "unknown"


def _load_env_file(env_file_path: str) -> dict[str, str]:
    """
    Charge un fichier .env et retourne un dictionnaire des variables.

    Args:
        env_file_path: Chemin vers le fichier .env

    Returns:
        Dictionnaire {variable_name: value}

    Notes:
        - Ignore les commentaires (#)
        - Ignore les lignes vides
        - Support des valeurs entre guillemets
    """
    env_vars = {}

    with open(env_file_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Ignorer commentaires et lignes vides
            if not line or line.startswith("#"):
                continue

            # Parser ligne: VAR=value
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Enlever les guillemets si présents
                value = value.strip('"').strip("'")

                env_vars[key] = value

    return env_vars


def get_setup_summary(setup_metadata: dict) -> str:
    """
    Génère un résumé lisible du setup.

    Args:
        setup_metadata: Résultat de detect_active_setup()

    Returns:
        Résumé formaté du setup
    """
    lines = [
        f"Setup: {setup_metadata['setup_name']}",
        f"Config file: {setup_metadata['models_env_file']}",
        "",
        "Models:",
    ]

    for model_type, model_info in setup_metadata["models"].items():
        model_name = os.path.basename(model_info["path"])
        lines.append(f"  {model_type.capitalize()}:")
        lines.append(f"    - Model: {model_name}")
        lines.append(f"    - Quantization: {model_info['quantization']}")

        if "ctx_size" in model_info:
            lines.append(f"    - Context size: {model_info['ctx_size']}")
        if model_info.get("extra_params"):
            lines.append(f"    - Extra params: {model_info['extra_params']}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test du module
    try:
        metadata = detect_active_setup()
        print("✅ Setup detected successfully!\n")
        print(get_setup_summary(metadata))
    except Exception as e:
        print(f"❌ Error: {e}")
