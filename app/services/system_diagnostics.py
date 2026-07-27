import importlib.metadata
import json
import shutil
import sqlite3
import stat
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import BACKUP_CONFIG_FILE
from app.config import BACKUP_DIR
from app.config import CLIENT_VIABILITY_FILE
from app.config import CONFIG_DIR
from app.config import CONTRACTS_DIR
from app.config import CONTRACTS_INDEX_FILE
from app.config import DATABASE_URL
from app.config import EQUIPMENT_CATALOG_FILE
from app.config import LOGIN_ATTEMPTS_FILE
from app.config import MAP_CONFIG_FILE
from app.config import PRODUCT_CATALOG_FILE
from app.config import HISTORY_FILE
from app.config import PREFERENCES_FILE
from app.config import PROFILES_FILE
from app.config import SESSIONS_FILE
from app.config import USERS_FILE
from app.services.data_loader import arquivos_dados_obrigatorios
from app.version import get_app_version


AUTHORITATIVE_JSON_FILES = (
    USERS_FILE,
    PROFILES_FILE,
    SESSIONS_FILE,
    LOGIN_ATTEMPTS_FILE,
    CONTRACTS_INDEX_FILE,
    EQUIPMENT_CATALOG_FILE,
    PRODUCT_CATALOG_FILE,
    CLIENT_VIABILITY_FILE,
    BACKUP_CONFIG_FILE,
    MAP_CONFIG_FILE,
    PREFERENCES_FILE,
    HISTORY_FILE,
    CONFIG_DIR / "finance" / "payments.json",
    CONFIG_DIR / "finance" / "agreements.json",
    CONFIG_DIR / "finance" / "alerts_config.json",
    CONFIG_DIR / "feasibility_history" / "records.json",
    CONFIG_DIR / "feasibility_history" / "imports.json",
    CONFIG_DIR / "feasibility_history" / "revisions.json",
)

SENSITIVE_FILES = {
    USERS_FILE,
    PROFILES_FILE,
    SESSIONS_FILE,
    LOGIN_ATTEMPTS_FILE,
    BACKUP_CONFIG_FILE,
    MAP_CONFIG_FILE,
}


def _item(category, name, status, detail=""):
    return {
        "Categoria": category,
        "Item": name,
        "Status": status,
        "Detalhe": detail,
    }


def _database_path(database_url=None):
    url = make_url(database_url or DATABASE_URL)
    return Path(url.database or "rede.db")


def verificar_jsons(paths=None):
    results = []
    for path in paths or AUTHORITATIVE_JSON_FILES:
        path = Path(path)
        if not path.exists():
            results.append(_item("JSON", str(path), "Ausente"))
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
            results.append(_item("JSON", str(path), "OK"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            results.append(_item("JSON", str(path), "Erro", str(error)))
    return results


def verificar_sqlite(path=None):
    path = Path(path or _database_path())
    if not path.exists():
        return [_item("SQLite", str(path), "Ausente")]

    try:
        connection = sqlite3.connect(
            f"file:{path.resolve()}?mode=ro",
            uri=True,
            timeout=30,
        )
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            quick_check = connection.execute("PRAGMA quick_check").fetchone()
            foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        return [_item("SQLite", str(path), "Erro", str(error))]

    status = "OK" if quick_check and quick_check[0] == "ok" else "Erro"
    detail = (
        f"quick_check={quick_check[0] if quick_check else 'sem retorno'}; "
        f"foreign_keys={foreign_keys[0] if foreign_keys else '?'}; "
        f"journal={journal_mode[0] if journal_mode else '?'}"
    )
    return [_item("SQLite", str(path), status, detail)]


def verificar_arquivos_obrigatorios(required=None):
    required = required or [
        (entry["nome"], Path(entry["caminho"]))
        for entry in arquivos_dados_obrigatorios()
    ]
    return [
        _item(
            "Dados",
            name,
            "OK" if Path(path).exists() else "Ausente",
            str(path),
        )
        for name, path in required
    ]


def verificar_espaco(base_dir="."):
    usage = shutil.disk_usage(Path(base_dir))
    free_percent = usage.free / usage.total * 100 if usage.total else 0
    status = (
        "Erro"
        if usage.free < 5 * 1024 ** 3
        else "Atenção"
        if free_percent < 15
        else "OK"
    )
    detail = (
        f"{usage.free / 1024 ** 3:.1f} GB livres "
        f"({free_percent:.1f}% do volume)"
    )
    return [_item("Disco", str(Path(base_dir).resolve()), status, detail)]


def verificar_backup(backup_dir=None, now=None, max_age_hours=48):
    backup_dir = Path(backup_dir or BACKUP_DIR)
    backups = sorted(
        backup_dir.glob("sgs_backup_*.zip")
        if backup_dir.exists()
        else [],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not backups:
        return [_item("Backup", str(backup_dir), "Atenção", "Nenhum backup encontrado.")]

    now = now or datetime.now()
    modified = datetime.fromtimestamp(backups[0].stat().st_mtime)
    age_hours = (now - modified).total_seconds() / 3600
    status = "OK" if age_hours <= max_age_hours else "Atenção"
    return [
        _item(
            "Backup",
            backups[0].name,
            status,
            f"Último backup há {age_hours:.1f} hora(s).",
        )
    ]


def verificar_permissoes(paths=None):
    paths = paths or [
        CONTRACTS_DIR,
        *AUTHORITATIVE_JSON_FILES,
        _database_path(),
    ]
    results = []
    sensitive = {Path(path) for path in SENSITIVE_FILES}

    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        mode = stat.S_IMODE(path.stat().st_mode)
        unsafe = (
            bool(mode & 0o007)
            or bool(mode & 0o020)
        )
        if path.is_file() and path in sensitive:
            unsafe = unsafe or bool(mode & 0o077)
        status = "Atenção" if unsafe else "OK"
        results.append(
            _item(
                "Permissões",
                str(path),
                status,
                oct(mode),
            )
        )
    return results


def verificar_dependencias(requirements_path="requirements.txt"):
    requirements_path = Path(requirements_path)
    if not requirements_path.exists():
        return [_item("Dependências", str(requirements_path), "Ausente")]

    missing = []
    divergent = []
    for raw_line in requirements_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        package, expected = line.split("==", 1)
        try:
            installed = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            missing.append(package)
            continue
        if installed != expected:
            divergent.append(f"{package}={installed} (esperado {expected})")

    if missing or divergent:
        detail = "; ".join(
            [
                f"ausentes: {', '.join(missing)}" if missing else "",
                f"divergentes: {', '.join(divergent)}" if divergent else "",
            ]
        ).strip("; ")
        return [_item("Dependências", "requirements.txt", "Atenção", detail)]

    return [_item("Dependências", "requirements.txt", "OK", "Versões instaladas conferidas.")]


def executar_diagnostico(
    *,
    base_dir=".",
    json_paths=None,
    database_path=None,
    required=None,
    backup_dir=None,
    requirements_path="requirements.txt",
):
    items = [
        _item("Aplicação", "Versão", "OK", get_app_version()),
        *verificar_jsons(json_paths),
        *verificar_sqlite(database_path),
        *verificar_arquivos_obrigatorios(required),
        *verificar_espaco(base_dir),
        *verificar_backup(backup_dir),
        *verificar_permissoes(),
        *verificar_dependencias(requirements_path),
    ]
    return {
        "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "saudavel": not any(item["Status"] == "Erro" for item in items),
        "itens": items,
    }
