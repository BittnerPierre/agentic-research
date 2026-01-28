"""Configuration management for agentic-research."""

import logging
import os
import threading
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# Load environment variables from .env file
try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv())
except ImportError:
    pass  # python-dotenv not available, skip loading


class VectorStoreConfig(BaseModel):
    """Configuration for vector store."""

    name: str = Field(default="Agentic Research Vector Store")
    description: str = Field(default="Vector store for research")
    expires_after_days: int = Field(default=30)
    vector_store_id: str = Field(default="")


class VectorSearchConfig(BaseModel):
    """Configuration for vector search collections and defaults."""

    provider: str = Field(default="local")
    index_name: str = Field(default="agentic-research")
    embedding_function: str = Field(default="sentence-transformers:all-MiniLM-L6-v2")
    chunk_size: int = Field(default=800)
    chunk_overlap: int = Field(default=120)
    chroma_host: str = Field(default="127.0.0.1")
    chroma_port: int = Field(default=8000)
    chroma_ssl: bool = Field(default=False)
    top_k: int = Field(default=5)
    score_threshold: float | None = Field(default=None)


class VectorMCPConfig(BaseModel):
    """Configuration for launching a vector search MCP server."""

    command: str = Field(default="uvx")
    args: list[str] = Field(default_factory=lambda: ["chroma-mcp"])
    tool_allowlist: list[str] = Field(
        default_factory=lambda: ["chroma_query_documents", "chroma_get_documents"]
    )
    client_timeout_seconds: float = Field(default=30.0)


class DataConfig(BaseModel):
    """Configuration for data sources."""

    urls_file: str = Field(default="urls.txt")
    knowledge_db_path: str = Field(default="data/knowledge_db.json")
    local_storage_dir: str = Field(default="data/")


class DebugConfig(BaseModel):
    """Configuration for debug mode."""

    enabled: bool = Field(default=False)
    output_dir: str = Field(default="debug_output")
    save_reports: bool = Field(default=True)


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    silence_third_party: bool = Field(default=True)
    third_party_level: str = Field(default="ERROR")


class MCPConfig(BaseModel):
    """Configuration for MCP (Model Context Protocol).

    Note: http_timeout_seconds is available but not exposed in config.yaml since
    the default (5.0s) is sufficient for HTTP connection establishment to localhost.
    Only client_timeout_seconds needs tuning for long-running tool operations.
    """

    server_host: str = Field(
        default="0.0.0.0",
        description="Host interface for the DataPrep MCP server",
    )
    server_port: int = Field(
        default=8001,
        description="Port for the DataPrep MCP server",
    )
    client_timeout_seconds: float = Field(
        default=10.0,
        description="Timeout for MCP tool execution (e.g., upload_files_to_vectorstore)"
    )
    http_timeout_seconds: float = Field(
        default=5.0,
        description="Timeout for HTTP connection to MCP server (usually localhost, rarely needs tuning)"
    )


class ModelsConfig(BaseModel):
    """Configuration for OpenAI."""

    research_model: str = Field(default="openai/gpt-4.1-mini")
    planning_model: str = Field(default="openai/gpt-4.1-mini")
    search_model: str = Field(default="openai/gpt-4.1-mini")
    writer_model: str = Field(default="litellm/mistral/mistral-medium-latest")
    knowledge_preparation_model: str = Field(default="litellm/mistral/mistral-medium-latest")
    # model: str = Field(default="openai/gpt-4.1-mini")
    # reasoning_model: str = Field(default="openai/o3-mini")


class ManagerConfig(BaseModel):
    """Configuration for manager selection."""

    default_manager: str = Field(default="agentic_manager")


class AgentsConfig(BaseModel):
    """Configuration for agents."""

    max_search_plan: str = Field(default="8-12")
    output_dir: str = Field(default="output/")


class Config(BaseModel):
    """Main configuration class."""

    config_name: str
    vector_store: VectorStoreConfig
    vector_search: VectorSearchConfig = Field(default_factory=VectorSearchConfig)
    vector_mcp: VectorMCPConfig = Field(default_factory=VectorMCPConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    debug: DebugConfig = Field(default_factory=DebugConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    manager: ManagerConfig = Field(default_factory=ManagerConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)


class ConfigManager:
    """Manages configuration loading with environment variable override."""

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            # Par défaut, chercher config.yaml dans le dossier du projet
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config.yaml"
            self.config_file_name = "config.yaml"
        else:
            self.config_file_name = config_path.name

        self.config_path = config_path
        self._config: Config | None = None

    def load_config(self) -> Config:
        """Load configuration from YAML file with environment variable overrides."""
        if self._config is not None:
            return self._config

        # Charger la configuration depuis le fichier YAML
        config_data = self._load_yaml_config()

        # Permettre l'override via les variables d'environnement
        config_data = self._apply_env_overrides(config_data)

        # Valider et créer l'objet de configuration
        self._config = Config(**config_data)
        return self._config

    def _load_yaml_config(self) -> dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _apply_env_overrides(self, config_data: dict[str, Any]) -> dict[str, Any]:
        """Apply environment variable overrides to configuration."""
        # # Permettre l'override du vector store name via la variable d'environnement
        # vector_store_name = os.getenv("VECTOR_STORE_NAME")
        # if vector_store_name:
        #     if "vector_store" not in config_data:
        #         config_data["vector_store"] = {}
        #     config_data["vector_store"]["name"] = vector_store_name

        # Override du mode debug via variable d'environnement
        debug_enabled = os.getenv("DEBUG")
        if debug_enabled:
            if "debug" not in config_data:
                config_data["debug"] = {}
            config_data["debug"]["enabled"] = debug_enabled.lower() in ("true", "1", "yes", "on")

        # Override du manager par défaut via variable d'environnement
        default_manager = os.getenv("DEFAULT_MANAGER")
        if default_manager:
            if "manager" not in config_data:
                config_data["manager"] = {}
            config_data["manager"]["default_manager"] = default_manager

        return config_data

    @property
    def config(self) -> Config:
        """Get the loaded configuration."""
        if self._config is None:
            return self.load_config()
        return self._config


# Instance globale pour l'accès facile - sera initialisée via le pattern singleton
_global_config_manager: ConfigManager | None = None
_config_lock = threading.Lock()
_config_access_logged = False


def get_config(config_file: str | None = None) -> Config:
    """Get the global configuration instance with singleton pattern.
    Thread-safe implementation using double-checked locking pattern.

    Args:
        config_file: Optional path to configuration file. If None, uses default 'config.yaml'.
                    If provided and differs from already loaded config, shows warning.

    Returns:
        Config: The configuration instance.
    """
    global _global_config_manager

    logger = logging.getLogger("agentic-research")

    # Premier check (performance optimization) - pas besoin de lock si déjà initialisé
    global _config_access_logged
    if _global_config_manager is not None:
        if config_file is None:
            # Appel sans paramètre (module) -> Normal, pas de message
            if not _config_access_logged:
                logger.debug(
                    f"Accès à la configuration existante: {_global_config_manager.config_file_name}"
                )
                _config_access_logged = True
            return _global_config_manager.config
        elif _global_config_manager.config_file_name == config_file:
            # Même fichier demandé -> Normal
            if not _config_access_logged:
                logger.debug(f"Configuration déjà initialisée avec le fichier: {config_file}")
                _config_access_logged = True
            return _global_config_manager.config
        else:
            # Fichier différent demandé (main qui arrive après) -> Warning
            logger.warning(
                f"Configuration déjà initialisée avec '{_global_config_manager.config_file_name}', "
                f"impossible de charger '{config_file}'. Utilisation de la configuration existante."
            )
            return _global_config_manager.config

    # Double-checked locking pattern pour thread safety
    with _config_lock:
        # Deuxième check dans le lock au cas où un autre thread l'aurait initialisé
        if _global_config_manager is None:
            # Laisser ConfigManager gérer le chemin par défaut si config_file est None
            if config_file is not None:
                project_root = Path(__file__).parent.parent
                config_path = project_root / config_file
                _global_config_manager = ConfigManager(config_path)
            else:
                _global_config_manager = ConfigManager()  # Utilise le défaut de ConfigManager

            logger.info(
                f"Configuration initialisée avec le fichier: {_global_config_manager.config_file_name}"
            )

        return _global_config_manager.config


def get_vector_store_name() -> str:
    """Get the vector store ID from configuration."""
    return get_config().vector_store.name
