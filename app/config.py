import os
from pathlib import Path


def env_path(name, default):
    return Path(os.getenv(name, default))


DATA_DIR = env_path("SNMPC_DATA_DIR", ".")
IMPORTS_DIR = env_path("SNMPC_IMPORTS_DIR", str(DATA_DIR / "imports"))
CONFIG_DIR = env_path("SNMPC_CONFIG_DIR", str(DATA_DIR / "config"))
CACHE_DIR = env_path("SNMPC_CACHE_DIR", str(DATA_DIR / "cache"))
BACKUP_DIR = env_path("SNMPC_BACKUP_DIR", str(DATA_DIR / "backups"))
ARCHIVE_DIR = env_path("SNMPC_ARCHIVE_DIR", str(IMPORTS_DIR / "archive"))
TMP_IMPORTS_DIR = env_path("SNMPC_TMP_IMPORTS_DIR", str(IMPORTS_DIR / "tmp"))

DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{DATA_DIR / 'rede.db'}"

USERS_FILE = env_path("SNMPC_USERS_FILE", str(CONFIG_DIR / "users.json"))
PROFILES_FILE = env_path("SNMPC_PROFILES_FILE", str(CONFIG_DIR / "profiles.json"))
SESSIONS_FILE = env_path("SNMPC_SESSIONS_FILE", str(CONFIG_DIR / "sessions.json"))
LOGIN_ATTEMPTS_FILE = env_path(
    "SNMPC_LOGIN_ATTEMPTS_FILE",
    str(CONFIG_DIR / "login_attempts.json")
)
PREFERENCES_FILE = env_path(
    "SNMPC_PREFERENCES_FILE",
    str(CONFIG_DIR / "user_preferences.json")
)
HISTORY_FILE = env_path(
    "SNMPC_HISTORY_FILE",
    str(CONFIG_DIR / "import_history.json")
)
LOG_DIR = env_path("SNMPC_LOG_DIR", str(CONFIG_DIR / "logs"))
AUTH_LOG_FILE = env_path("SNMPC_AUTH_LOG_FILE", str(LOG_DIR / "usuarios.jsonl"))
SYSTEM_LOG_FILE = env_path("SNMPC_SYSTEM_LOG_FILE", str(LOG_DIR / "sistema.jsonl"))
CONTRACTS_DIR = env_path(
    "SNMPC_CONTRACTS_DIR",
    str(DATA_DIR / "contracts")
)
CONTRACTS_INDEX_FILE = env_path(
    "SNMPC_CONTRACTS_INDEX_FILE",
    str(CONFIG_DIR / "site_contracts.json")
)
EQUIPMENT_CATALOG_FILE = env_path(
    "SNMPC_EQUIPMENT_CATALOG_FILE",
    str(CONFIG_DIR / "equipment_catalog.json")
)
PRODUCT_CATALOG_FILE = env_path(
    "SNMPC_PRODUCT_CATALOG_FILE",
    str(CONFIG_DIR / "product_catalog.json")
)
BACKUP_CONFIG_FILE = env_path(
    "SNMPC_BACKUP_CONFIG_FILE",
    str(CONFIG_DIR / "backup_config.json")
)
MAP_CONFIG_FILE = env_path(
    "SNMPC_MAP_CONFIG_FILE",
    str(CONFIG_DIR / "map_config.json")
)
CLIENT_VIABILITY_FILE = env_path(
    "SNMPC_CLIENT_VIABILITY_FILE",
    str(CONFIG_DIR / "client_viability.json")
)

CLIENTES_FILE = env_path("SNMPC_CLIENTES_FILE", str(IMPORTS_DIR / "clientes.xlsx"))
GEOCODING_CACHE_FILE = env_path(
    "SNMPC_GEOCODING_CACHE_FILE",
    str(CACHE_DIR / "geocoding_clientes.json")
)
MAP_CACHE_FILE = env_path(
    "SNMPC_MAP_CACHE_FILE",
    str(CACHE_DIR / "mapa_clientes.json")
)
ELEVATION_CACHE_FILE = env_path(
    "SNMPC_ELEVATION_CACHE_FILE",
    str(CACHE_DIR / "elevation_cache.json")
)
STRUCTURE_LINKS_CACHE_FILE = env_path(
    "SNMPC_STRUCTURE_LINKS_CACHE_FILE",
    str(CACHE_DIR / "structure_links.json")
)


def candidate_import_file(*names):
    for name in names:
        path = IMPORTS_DIR / name

        if path.exists():
            return path

    return IMPORTS_DIR / names[0]
